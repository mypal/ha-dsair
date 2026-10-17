# Pinned Home Assistant Core 2026.9.4 turn-on delegation methods.
# Source: https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/climate/__init__.py
# Home Assistant Core: Apache-2.0; see LICENSE.home-assistant.
# Excerpt: imports omitted and formatting normalized for the isolated harness.
class ClimateEntity:

    def turn_on(self) -> None:
        """Turn the entity on."""
        raise NotImplementedError

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if type(self).turn_on is not ClimateEntity.turn_on:
            await self.hass.async_add_executor_job(self.turn_on)
            return
        if len(self.hvac_modes) == 2 and HVACMode.OFF in self.hvac_modes:
            for mode in self.hvac_modes:
                if mode != HVACMode.OFF:
                    await self.async_set_hvac_mode(mode)
                    return
        for mode in (HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL):
            if mode not in self.hvac_modes:
                continue
            await self.async_set_hvac_mode(mode)
            return
        raise NotImplementedError
