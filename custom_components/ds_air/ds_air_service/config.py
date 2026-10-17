class Config:
    gateway_id: str = ""
    is_new_version: bool = False
    is_c611: bool = True  # 金制空气c611 or ds-air b611
    is_d611: bool = False  # 金制空气d611
    is_f611: bool = False  # 金制空气f611

    @property
    def is_kinsei(self) -> bool:
        """Kinsei status flags differ from the older B611 temperature layout."""
        return self.is_c611 or self.is_d611 or self.is_f611
