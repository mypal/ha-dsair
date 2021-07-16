# Daikin DS-AIR Custom Component For Home Assistant

此项目是Home Assistant平台[DS-AIR](https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/)以及[金制空气](https://www.daikin-china.com.cn/newha/products/4/19/jzkq/)自定义组件的实现

支持的网关设备型号为DTA117B611/DTA117C611，其他网关的支持情况未知

# 支持设备

* 空调
* 空气传感器

# 不支持设备

* 睡眠传感器
* 晴天轮
* 转角卫士
* 金制家中用防护组件
* 显示屏(黑奢系列)

# 接入方法

1. 将项目ha-air目录部署到自定义组件目录，一般路径为```~/.homeassistant/custom_components/```  
   或使用hacs载入自定义存储库，设置URL```https://github.com/mypal/ha-dsair``` ，类别 ```集成```
2. 本集成已支持ha可视化配置，在配置-集成-添加集成中选择```DS-AIR``` ，依次填入网关IP、端口号、设备型号提交即可

# TODO

根据APP反解显示，网关可控制新风、地暖、HD(不知道是个啥设备)、新版空调、老版空调和浴室设备。由于我家只有新版室内机，所以目前只实现了这个。其他设备实现没写完，理论上都不能够支持。

# 开发过程

本组件开发过程可在[blog](https://www.mypal.wang/blog/lun-yi-ci-jia-yong-kong-diao-jie-ru-hazhe-teng-jing-li/)查看
