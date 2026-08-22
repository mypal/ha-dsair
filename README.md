# Daikin DS-AIR Custom Component For Home Assistant

此项目是 Home Assistant 平台 [DS-AIR](https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/) 以及 [金制空气](https://www.daikin-china.com.cn/newha/products/4/19/jzkq/) 自定义组件的实现。

---

## 🌟 支持设备与网关型号

### 支持网关
* **大金金制智联 Smart Mesh Hub**（支持 TCP 8009 本地遥测与 MQTT 云端直控）
* **大金多联机/VRV 网关**：`DTA117B611`、`DTA117C611`、`DTA117D611`

### 支持设备类型
* **家用分体空调 (RA)**：已通过实机全面测试（如 **E-Max 7 系列 FTXR172WC-N1** 等）
* **VRV / 多联机中央空调**
* **新风系统 / 小型新风 (MiniVAM)**
* **金制地暖 / 卫浴空调 / HD 设备**
* **空气质量传感器**（温度、湿度、PM2.5、CO2、TVOC、VOC、甲醛 HCHO）

---

## 🚀 核心特性

* **本地 + 云端双模无缝集成**：
  * **本地局域网通讯 (TCP 8008 / 8009)**：实时读取设备基础信息、节点拓扑与传感器遥测数据，稳定低延迟；
  * **大金云端直连 (mTLS + MQTT)**：通过金制空气云端 API 及 EMQX MQTT Broker 实现远程与本地控制，与官方手机 App 双向秒级同步状态。
* **完整的空调控制与状态展示**：
  * 开关控制、目标温度调节；
  * 运行模式切换（制冷、制热、除湿、送风、自动、关闭）；
  * 多档风速切换（自动、强、中、弱、静音等）与上下摆风设置。
* **配置流与选项流友好支持**：
  * 支持通过 UI 界面自动发现并配置网关；
  * 选项中支持关联外部温湿度传感器；
  * 选项中支持直接绑定金制空气云端账号进行 MQTT 状态同步。

---

## 📦 接入方法

### 1. 安装

#### 方法一：通过 HACS（推荐）
点击下方按钮直接添加自定义存储库：

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mypal&repository=ha-dsair&category=integration)

然后在 HACS 中搜索并下载安装 **DS-AIR**。

#### 方法二：手动安装
将本项目中的 `custom_components/ds_air` 目录直接复制到 Home Assistant 配置目录下的 `custom_components/` 中，并重启 Home Assistant。

---

### 2. 配置

1. 进入 Home Assistant **设置 -> 设备与服务 -> 添加集成**，搜索 **DS-AIR**（或点击下方按钮）：
   
   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ds_air)

2. 输入网关 IP（如 `192.168.x.x`）、端口号（VRV 默认 `8008`，Smart Mesh Hub 默认 `8009`）及设备型号即可完成添加。
3. （可选）在集成选项中点击 **「绑定金制空气云端账号」** 输入手机号与密码，即可开启云端 MQTT 双向同步直控。

---

## 📝 鸣谢与参考

* 原项目与开发历程参考：[mypal's blog](https://www.mypal.wang/blog/lun-yi-ci-jia-yong-kong-diao-jie-ru-hazhe-teng-jing-li/)

