from enum import IntFlag


class GatewayFeature(IntFlag):
    EXTENDED_STATUS_FLAGS = 1 << 0
    ROOM_INFO_V1 = 1 << 1
    QUIET_FAN = 1 << 2
    NO_RECOMMENDED_TEMP = 1 << 3
    NO_CURRENT_TEMP = 1 << 4

class Config:
    gateway_id: str = ""
    is_new_version: bool = False
    gateway_features: GatewayFeature = GatewayFeature(0)

    def supports(self, feature: GatewayFeature) -> bool:
        return bool(self.gateway_features & feature)
