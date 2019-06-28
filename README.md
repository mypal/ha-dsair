# Daikin DS-AIR Custom Component For Home Assistant

此项目是Home Assistant平台[DS-AIR](https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/)自定义组件的实现

支持的网关设备型号为DTA117B611，其他网关的支持情况未知

由于家里只有中央空调，对于老款型号、浴室系列空调等等没有测试条件。理论上也能部分支持

# 接入方法

1. 将项目ha-air目录部署到自定义组件目录，一般路径为```~/.homeassistant/custom_components/``
2. 在配置文件```~/.homeassistant/configuration.yaml``中添加配置  
```yaml
climate:
  - platform: ds_air
    host: 192.168.1.150  # 空调网关IP地址，默认：192.168.1.150
    port: 8008           # 网关端口号，默认：8008
```
3. 重启HA服务

# TODO

根据APP反解显示，网关可控制新风、地暖、HD(不知道是个啥设备)、新版空调、老版空调和浴室设备。由于我家只有新版室内机，所以目前只实现了这个。其他设备实现没写完，理论上都不能够支持。

# 开发过程

本组件开发过程可在[blog](https://www.mypal.wang/blog/lun-yi-ci-jia-yong-kong-diao-jie-ru-hazhe-teng-jing-li/)查看
