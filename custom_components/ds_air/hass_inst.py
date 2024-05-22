class GetHass:
    HASS = None

    @staticmethod
    def set_hass(hass):
        GetHass.HASS = hass

    @staticmethod
    def get_hash():
        return GetHass.HASS
