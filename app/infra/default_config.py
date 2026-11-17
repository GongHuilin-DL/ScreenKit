"""默认配置。所有可调参数集中于此，便于统一读取与覆盖。""" 
DEFAULT_CONFIG = { 
"app": {"name": "ScreenKit", "version": "0.1.0"}, 
"capture": {"default_fps": 30, "image_format": "png", "image_quality": 95}, 
"recording": {"video_format": "mp4", "codec": "h264", "crf": 23, "preset": "fast"}, 
"audio": {"sample_rate": 48000, "channels": 2, "record_system": True, "record_mic": False}, 
"export": {"formats": ["mp4", "avi", "wmv"]}, 
"scrollshot": {"scroll_step": 0.8, "wait_after_scroll": 0.4, "overlap_threshold": 0.2}, 
"paths": {"output_dir": "output", "temp_dir": "temp", "log_dir": "logs"}, 
} 
