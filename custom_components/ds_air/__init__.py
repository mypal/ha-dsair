"""
Platform for DS-AIR of Daikin
https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""

if __name__ == '__main__':
    from custom_components.ds_air.ds_air_service.service import Service
    Service.hand_shake()
