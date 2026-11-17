"""滚动截图拼接器：固定元素剥离（顶部+右侧）+ 多策略 + 历史先验防错位。"""
import shutil
import tempfile
from enum import Enum
from pathlib import Path

import numpy as np

from app.infra.logger import get_logger

logger = get_logger("scrollshot.stitcher")

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    cv2 = None
    _HAS_CV2 = False

try:
    import scrollweave
    _HAS_SCROLLWEAVE = True
except ImportError:
    scrollweave = None
    _HAS_SCROLLWEAVE = False


class MatchStrategy(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    ROBUST = "robust"
    FEATURE = "feature"


class MatchResult:
    __slots__ = ("offset", "confidence", "method")

    def __init__(self, offset, confidence, method):
        self.offset = offset
        self.confidence = confidence
        self.method = method

    @property
    def accepted(self):
        return self.offset is not None

    def __repr__(self):
        if not self.accepted:
            return f"MatchResult(rejected, method={self.method})"
        return f"MatchResult(offset={self.offset}, conf={self.confidence:.2f}, method={self.method})"


def _reject(method):
    return MatchResult(None, 0.0, method)


class Stitcher:
    MAX_FIXED_TOP_RATIO = 0.15
    MAX_FIXED_TOP_PIXELS = 150       # 固定顶部最高不超过 150 像素
    MAX_FIXED_RIGHT_RATIO = 0.20     # 右侧固定区域最多占 20% 宽度
    MAX_BOTTOM_CROP = 500
    WHITE_STREAK_THRESHOLD = 10
    MIN_OVERLAP = 30
    OFFSET_TOLERANCE = 150           # 历史先验容差：偏移量突变超过 150 像素视为错位

    TEMPLATE_CONF_THRESHOLD = 0.35
    ROW_SIG_MAE_THRESHOLD = 8.0
    ORB_MAD_THRESHOLD = 10.0

    def __init__(self, strategy=MatchStrategy.BALANCED, prefer_scrollweave=False):
        self.strategy = strategy if isinstance(strategy, MatchStrategy) else MatchStrategy(strategy)
        self.prefer_scrollweave = prefer_scrollweave and _HAS_SCROLLWEAVE
        self._skipped_frames = 0
        logger.info("Stitcher 初始化: strategy=%s", self.strategy.value)

    @property
    def skipped_frames(self):
        return self._skipped_frames

    def stitch(self, frames, scroll_positions=None):
        if len(frames) == 0:
            raise ValueError("没有可拼接的帧")
        if len(frames) == 1:
            return self._to_pil(frames[0])

        if self.prefer_scrollweave:
            try:
                return self._stitch_scrollweave(frames, scroll_positions)
            except Exception:
                logger.exception("scrollweave 拼接失败，回退到 OpenCV")

        if _HAS_CV2:
            return self._stitch_cv2(frames)

        raise RuntimeError("scrollweave 与 OpenCV 均不可用，无法拼接")

    # --- scrollweave ---

    def _stitch_scrollweave(self, frames, scroll_positions):
        tmp_dir = Path(tempfile.mkdtemp(prefix="stitch_sw_"))
        paths = []
        try:
            for i, frame in enumerate(frames):
                pil = self._to_pil(frame)
                path = tmp_dir / f"frame_{i:04d}.png"
                pil.save(path, "PNG")
                paths.append(str(path))

            kwargs = {}
            if scroll_positions is not None and len(scroll_positions) == len(frames):
                kwargs["scroll"] = list(scroll_positions)
            result = scrollweave.stitch_layered(paths, **kwargs)
            out_path = tmp_dir / "stitched.png"
            result.save(str(out_path))
            from PIL import Image
            with Image.open(out_path) as im:
                return im.copy()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --- OpenCV 主流程 ---

    def _stitch_cv2(self, frames):
        self._skipped_frames = 0
        images = [self._to_cv2_bgr(f) for f in frames]

        # 1. 裁掉系统滚动条区域（右侧固定的 20 像素）
        cropped = []
        for img in images:
            if img.shape[1] > 30:
                cropped.append(img[:, :-20])
            else:
                cropped.append(img)

        # 2. 检测固定顶部和右侧浮动栏
        top_fixed_h = 0
        right_fixed_w = 0
        if len(cropped) >= 2:
            top_fixed_h = self._detect_fixed_top(cropped[0], cropped[1])
            right_fixed_w = self._detect_fixed_right(cropped[0], cropped[1])
            
        # 如果有右侧固定区域，直接把它从每一帧里切掉，不参与后续任何拼接
        if right_fixed_w > 0:
            logger.info("检测到右侧固定悬浮区域 %d 列，已剥离", right_fixed_w)
            w = cropped[0].shape[1]
            keep_w = max(1, w - right_fixed_w)
            cropped = [img[:, :keep_w] for img in cropped]

        if top_fixed_h > 0:
            logger.info("检测到顶部固定元素 %d 行，拼接时将跳过", top_fixed_h)

        # 3. 逐帧匹配与拼接
        pieces = [cropped[0]]
        last_valid_offset = None

        for i in range(1, len(cropped)):
            prev = cropped[i - 1]
            curr = cropped[i]

            result = self._estimate_offset(prev, curr, last_valid_offset, top_fixed_h)
            if not result.accepted:
                self._skipped_frames += 1
                logger.debug("第 %d 帧被拒绝: %s", i, result)
                continue

            offset = result.offset
            if offset >= curr.shape[0]:
                self._skipped_frames += 1
                continue

            last_valid_offset = offset
            start_y = max(offset, top_fixed_h)
            
            if start_y >= curr.shape[0]:
                self._skipped_frames += 1
                continue

            pieces.append(curr[start_y:, :])
            logger.debug("第 %d 帧拼接: offset=%d, method=%s", i, offset, result.method)

        # 4. 拼接与底部白边裁剪
        from PIL import Image
        if len(pieces) == 1:
            stitched = pieces[0]
        else:
            stitched = np.vstack(pieces)

        before_h = stitched.shape[0]
        stitched = self._crop_bottom_white(stitched)
        if stitched.shape[0] < before_h:
            logger.info("裁剪底部白边 %d 行", before_h - stitched.shape[0])

        if self._skipped_frames > 0:
            logger.warning("本次拼接共拒绝 %d 帧", self._skipped_frames)

        rgb = cv2.cvtColor(stitched, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    # --- 固定元素检测 ---

    def _detect_fixed_top(self, img1, img2):
        h = img1.shape[0]
        limit = min(int(h * self.MAX_FIXED_TOP_RATIO), self.MAX_FIXED_TOP_PIXELS)
        fixed_h = 0
        for y in range(5, limit, 5):
            diff = np.mean(np.abs(img1[:y].astype(np.int16) - img2[:y].astype(np.int16)))
            if diff < 3.0:
                # 排除纯色背景
                mean_std = np.mean(np.std(img1[:y].astype(np.float32), axis=(0, 1)))
                if mean_std > 2.0:
                    fixed_h = y
                else:
                    break
            else:
                break
        return fixed_h

    def _detect_fixed_right(self, img1, img2):
        """检测右侧固定区域。通过比对列差异，找出右侧不动的部分。"""
        w = img1.shape[1]
        limit = int(w * self.MAX_FIXED_RIGHT_RATIO)
        if limit < 20:
            return 0
            
        col_diff = np.mean(np.abs(img1.astype(np.int16) - img2.astype(np.int16)), axis=0)
        
        fixed_w = 0
        for x in range(w - 5, w - limit, -5):
            if np.mean(col_diff[x:]) < 3.0:
                fixed_w = w - x
            else:
                break
        return fixed_w

    # --- 策略调度 ---

    def _estimate_offset(self, prev, curr, last_valid_offset, top_fixed_h):
        h = prev.shape[0]
        if h < 100:
            return _reject("too_small")

        diff = float(np.mean(np.abs(prev.astype(np.int16) - curr.astype(np.int16))))
        if diff < 1.0:
            return MatchResult(h, 1.0, "identical")

        result = _reject("none")

        if self.strategy == MatchStrategy.FAST:
            result = self._match_by_row_signature(prev, curr, last_valid_offset)
        elif self.strategy == MatchStrategy.BALANCED:
            result = self._match_by_template(prev, curr, last_valid_offset)
            if not result.accepted:
                result = self._match_by_row_signature(prev, curr, last_valid_offset)
        elif self.strategy == MatchStrategy.ROBUST:
            result = self._match_by_template(prev, curr, last_valid_offset)
            if not result.accepted:
                result = self._match_by_row_signature(prev, curr, last_valid_offset)
            if not result.accepted:
                result = self._match_by_orb(prev, curr, last_valid_offset)
        elif self.strategy == MatchStrategy.FEATURE:
            result = self._match_by_orb(prev, curr, last_valid_offset)
            if not result.accepted:
                result = self._match_by_template(prev, curr, last_valid_offset)

        # 兜底 1：画面差异大但匹配失败 → 用上次偏移
        if not result.accepted and last_valid_offset is not None and diff > 3.0:
            return MatchResult(last_valid_offset, 0.3, "fallback_last")

        # 兜底 2：固定元素拒绝
        if result.accepted and top_fixed_h > 0 and result.offset < top_fixed_h - 10:
            return _reject("fixed_element_reject")

        # 兜底 3：重叠太小
        if result.accepted and result.offset < self.MIN_OVERLAP:
            return _reject("overlap_too_small")

        return result

    # --- 匹配器 1：模板匹配 ---

    def _match_by_template(self, prev, curr, last_valid_offset):
        h = prev.shape[0]
        w = prev.shape[1]
        w_start = int(w * 0.15)
        w_end = int(w * 0.85)
        
        prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (5, 5), 0)
        curr_gray = cv2.GaussianBlur(curr_gray, (5, 5), 0)

        best = _reject("template")

        for ratio in (0.85, 0.65, 0.45, 0.25):
            t_start = int(h * ratio)
            t_end = t_start + int(h * 0.15)
            if t_end > h:
                continue
            tmp = prev_gray[t_start:t_end, w_start:w_end]
            
            if np.std(tmp) < 8.0:
                continue
                
            search_end = min(h, t_start + 200)
            search = curr_gray[:search_end, w_start:w_end]
            if search.shape[0] < tmp.shape[0]:
                continue
            
            res = cv2.matchTemplate(search, tmp, cv2.TM_SQDIFF_NORMED)
            
            # 遍历所有误差足够小的匹配点（可能匹配到多个重复卡片）
            loc = np.where(res <= self.TEMPLATE_CONF_THRESHOLD)
            if len(loc[0]) == 0:
                continue

            # 寻找与历史步长最接近的那个匹配点
            for i in range(len(loc[0])):
                pt_y = loc[0][i]
                pt_x = loc[1][i]
                val = res[pt_y, pt_x]
                
                scroll_delta = t_start - pt_y
                if scroll_delta <= 20:
                    continue
                    
                offset = h - scroll_delta
                
                # 先验检查：如果与历史偏移相差过大，大概率是匹配到了重复卡片，忽略
                if last_valid_offset is not None and abs(offset - last_valid_offset) > self.OFFSET_TOLERANCE:
                    continue
                    
                confidence = max(0.0, 1.0 - val)
                if confidence > best.confidence:
                    best = MatchResult(offset, confidence, "template")
                    
            if best.confidence > 0.85:
                break
        return best

    # --- 匹配器 2：行签名 ---

    def _match_by_row_signature(self, prev, curr, last_valid_offset):
        if prev.ndim == 3:
            prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
        else:
            prev_gray = prev
            curr_gray = curr

        prev_sig = prev_gray.astype(np.float32).mean(axis=1)
        curr_sig = curr_gray.astype(np.float32).mean(axis=1)
        prev_std = prev_gray.astype(np.float32).std(axis=1)
        curr_std = curr_gray.astype(np.float32).std(axis=1)

        h = min(len(prev_sig), len(curr_sig))
        if h < 20:
            return _reject("row_signature")

        best_overlap = None
        best_mae = float("inf")
        
        for overlap in range(self.MIN_OVERLAP, h - 20):
            a = prev_sig[-overlap:]
            b = curr_sig[:overlap]
            a_std = prev_std[-overlap:]
            b_std = curr_std[:overlap]
            
            valid_mask = (a_std > 2.0) & (b_std > 2.0)
            if np.sum(valid_mask) < 10:
                continue
                
            mae = float(np.mean(np.abs(a[valid_mask] - b[valid_mask])))
            offset = h - overlap
            
            # 先验惩罚：如果计算出的偏移与历史相差太大，增加误差惩罚，迫使算法避开重复卡片
            if last_valid_offset is not None and abs(offset - last_valid_offset) > self.OFFSET_TOLERANCE:
                mae += 20.0
                    
            if mae < best_mae:
                best_mae = mae
                best_overlap = overlap

        if best_overlap is None or best_mae > self.ROW_SIG_MAE_THRESHOLD:
            return _reject("row_signature")

        offset = h - best_overlap
        confidence = max(0.0, 1.0 - best_mae / self.ROW_SIG_MAE_THRESHOLD)
        return MatchResult(offset, confidence, "row_signature")

    # --- 匹配器 3：ORB 特征点 ---

    def _match_by_orb(self, prev, curr, last_valid_offset):
        orb = cv2.ORB_create(nfeatures=2000)
        kp1, des1 = orb.detectAndCompute(prev, None)
        kp2, des2 = orb.detectAndCompute(curr, None)
        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return _reject("orb")

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        if len(matches) < 10:
            return _reject("orb")

        dys = []
        for m in matches:
            y1 = kp1[m.queryIdx].pt[1]
            y2 = kp2[m.trainIdx].pt[1]
            x1 = kp1[m.queryIdx].pt[0]
            x2 = kp2[m.trainIdx].pt[0]
            if abs(x1 - x2) < 5 and y1 > y2:
                dys.append(y1 - y2)

        if len(dys) < 10:
            return _reject("orb")

        dys_arr = np.array(dys, dtype=np.float32)
        median = float(np.median(dys_arr))
        mad = float(np.median(np.abs(dys_arr - median)))
        
        offset = int(round(median))
        if offset <= 0 or offset >= curr.shape[0]:
            return _reject("orb")
            
        # 先验检查：如果偏移与历史步长差异过大，说明匹配到了重复区域
        if last_valid_offset is not None and abs(offset - last_valid_offset) > self.OFFSET_TOLERANCE:
             return _reject("orb_prior_mismatch")

        if mad > self.ORB_MAD_THRESHOLD:
            return _reject("orb")

        confidence = max(0.0, 1.0 - mad / self.ORB_MAD_THRESHOLD)
        return MatchResult(offset, confidence, "orb")

    # --- 底部白边裁剪 ---

    def _crop_bottom_white(self, img, white_thresh=250):
        h = img.shape[0]
        if h < 20:
            return img
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        row_means = np.mean(gray, axis=1)
        crop_y = h
        white_streak = 0
        lower_bound = max(h - self.MAX_BOTTOM_CROP, 0)
        for y in range(h - 1, lower_bound, -1):
            if row_means[y] > white_thresh:
                white_streak += 1
                if white_streak >= self.WHITE_STREAK_THRESHOLD:
                    crop_y = y + self.WHITE_STREAK_THRESHOLD
                    break
            else:
                white_streak = 0
        return img[:crop_y, :]

    # --- 工具 ---

    @staticmethod
    def _to_pil(frame):
        from PIL import Image
        if isinstance(frame, Image.Image):
            return frame
        arr = np.asarray(frame)
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[:, :, [2, 1, 0]]
        elif arr.ndim == 3 and arr.shape[2] == 3:
            arr = arr[:, :, ::-1]
        return Image.fromarray(arr.astype(np.uint8))

    @staticmethod
    def _to_cv2_bgr(frame):
        from PIL import Image
        if isinstance(frame, Image.Image):
            return cv2.cvtColor(np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR)
        arr = np.asarray(frame)
        if arr.ndim == 3 and arr.shape[2] == 4:
            return arr[:, :, :3].copy()
        return arr