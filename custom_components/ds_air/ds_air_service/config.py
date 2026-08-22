class Config:
    gateway_id: str = ""
    is_new_version: bool = False
    is_c611: bool = True  # 金制空气c611 or ds-air b611
    is_d611: bool = False  # 金制空气d611
    is_mesh: bool = False  # 金制智联 Mesh Hub / RA
    is_vrv: bool = True  # VRV 多联机集中网关
    detected_port: int = 8008  # 自动探测连接的端口 (8008 / 8009)
