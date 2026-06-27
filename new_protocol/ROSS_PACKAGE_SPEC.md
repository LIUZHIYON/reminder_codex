# ROS2 robot_* CI 打包规范 — 包项目结构

> 你的仓库必须满足本文档规范，才能被 CI 流水线自动编译成 .deb 并发布到 OTA 仓库。
> CI 脚本入口: `ci_build_deb.sh <pkg_name>`

---

## 一、三 种包类型

| 类型 | build_type | 编译方式 | 必须有 |
|------|-----------|---------|--------|
| **纯 Python 包** | `ament_python` | Nuitka → .so + colcon | `package.xml` + `setup.py` |
| **纯 msg/srv 包** | `ament_cmake` | CMake 编译 .msg → 运行时库 | `package.xml` + `CMakeLists.txt` |
| **C++ 包** | `ament_cmake` | colcon build + cmake | `package.xml` + `CMakeLists.txt` |

> **CI 会自动判断:** 有 `ament_cmake` → 跳过 Python 编译 + robot_utils 依赖注入

---

## 二、标准目录结构

### 2.1 纯 Python 包 (ament_python)

```
robot_vision/                          ← repo 根，命名 robot_<snake_case>
├── package.xml                        ← 必选
├── setup.py                           ← 必选
├── setup.cfg                          ← 必选 (colcon 要求)
├── resource/
│   └── robot_vision                   ← marker 文件 (colcon 要求，可为空)
├── robot_vision/                      ← 业务源码目录 (与 package name 一致)
│   ├── __init__.py                    ← 必选
│   ├── vision_node.py                 ← 业务 .py (会被 Nuitka 编译成 .so)
│   ├── detector.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── launch/                            ← 可选: launch 文件
│   └── vision.launch.py
├── config/                            ← 可选: yaml 配置文件
│   └── vision_params.yaml
├── data/                              ← 可选: 数据文件
│   └── model.pt
├── test/                              ← 可选 (CI 不会跑测试)
│   └── test_copyright.py
├── .gitignore
└── README.md                          ← 可选
```

**关键约束:**
- 源码目录名必须 = `package.xml` 的 `<name>` (如 `robot_vision/`)
- 目录严格放在 repo 根的平级，不是子目录
- CI 找源文件路径: `$WORKSPACE_DIR/src/$pkg_name/$pkg_name/*.py`

### 2.2 纯 msg/srv 包 (ament_cmake)

```
robot_car_control_msgs/
├── package.xml                        ← 必选
├── CMakeLists.txt                     ← 必选
├── msg/                               ← 消息定义
│   ├── ChassisData.msg
│   └── SerialStatus.msg
├── srv/                               ← 服务定义 (可选)
│   └── Calculate.srv
├── .gitignore
└── README.md
```

**不需要** `setup.py`、`__init__.py`、源码目录。

### 2.3 C++ 包 (ament_cmake)

```
robot_camera_cpp/
├── package.xml                        ← 必选
├── CMakeLists.txt                     ← 必选
├── include/                           ← 头文件
│   └── robot_camera_cpp/
│       └── camera_node.h
├── src/                               ← 源码
│   └── camera_node.cpp
├── .gitignore
└── README.md
```

---

## 三、关键文件规范

### 3.1 package.xml

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd"
            schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>robot_vision</name>                         <!-- 必须。下划线命名,不含- -->
  <version>0.0.0</version>                          <!-- 必须。首版填 0.0.0,CI 自动递增 -->
  <description>视觉检测模块</description>             <!-- 必须。会写入 deb control -->
  <maintainer email="your@email.com">你的名字</maintainer>
  <license>MIT</license>

  <build_type>ament_python</build_type>              <!-- Python 包必须 -->

  <!-- ROS2 依赖 (CI 会自动加 robot_utils,不必手动加) -->
  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>robot_interface</depend>                   <!-- 依赖其他 robot_* 包 -->

  <!-- 系统 apt 依赖 -->
  <exec_depend>python3-opencv</exec_depend>
  <exec_depend>python3-numpy</exec_depend>
</package>
```

**严格规则:**

| 规则 | 说明 |
|------|------|
| `<version>` 填 `0.0.0` | CI 自动对比 OTA 仓库,取 max +1 递增 |
| `<depend>` robot_xxx | CI 会转成 deb 依赖: `robot_xxx` → `robot-xxx` |
| `<exec_depend>` python3-xxx | CI 会写入 `Depends:` 字段,设备侧 apt 自动装 |
| `<description>` 必填 | deb control 的 Description 字段,不能空 |
| **不要手动加 robot_utils** | CI 自动注入,手动加会导致重复依赖 |
| C++ 包加 `<build_type>ament_cmake</build_type>` | CI 据此跳过 Python 编译 |

### 3.2 setup.py

```python
from setuptools import setup
import os, glob

package_name = 'robot_vision'                       # 必须 = package.xml 的 <name>

setup(
    name=package_name,
    version='0.0.0',                                # CI 自动同步 package.xml 版本
    packages=[package_name],                        # 必须。列出自有 Python 包
    include_package_data=True,                      # 必须。让 setuptools 读 MANIFEST.in
    package_data={
        package_name: ['*.so', '*.pyi'],            # 必须。Nuitka 产物全是 .so
    },
    data_files=[                                    # 可选。非 Python 文件放这里
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob.glob('launch/*.py')),                 # launch 文件
        (os.path.join('share', package_name, 'config'),
         glob.glob('config/*.yaml')),               # 配置文件
        # 注意:大文件(data/*.wav, model/*.pt)用 Path 对象 + os.path.join
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='你的名字',
    maintainer_email='your@email.com',
    description='视觉检测模块',
    license='MIT',
    entry_points={
        'console_scripts': [
            'vision_node = robot_vision.vision_node:main',
        ],
    },
)
```

**三个必选项，任何一个漏了都没 .so 进 deb:**

```python
include_package_data=True,              # ① 启用 MANIFEST.in
package_data={package_name: ['*.so']},  # ② 兜底规则
# MANIFEST.in:                          # ③ 文件清单 (见下节)
```

### 3.3 setup.cfg

```ini
[develop]
script_dir=$base/lib/robot_vision
[install]
install_scripts=$base/lib/robot_vision
```

### 3.4 MANIFEST.in (强烈推荐)

```
recursive-include robot_vision *.so
recursive-include robot_vision *.pyi
```

> 加上这个文件后，即使 `package_data` 漏配，setuptools 也靠它收集 .so。

### 3.5 CMakeLists.txt (仅 msg/srv 和 C++ 包)

**msg 包模板:**
```cmake
cmake_minimum_required(VERSION 3.8)
project(robot_car_control_msgs)

find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ChassisData.msg"
  "msg/SerialStatus.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
```

---

## 四、CI 流水线检查清单

新增包时，确认以下 8 项全部通过:

| # | 检查项 | 对应 CI 步骤 | 失败报错 |
|---|--------|-------------|---------|
| 1 | 源码在 `src/<pkg_name>/` 下 | Step 1 编译 | `包目录不存在` |
| 2 | `package.xml` 存在且 `<version>` 不空 | Step 0 bump | `取不到版本` |
| 3 | `setup.py` 存在 (Python 包) | Step 2 colcon | colcon 跳过该包 |
| 4 | `include_package_data=True` | Step 4 复制产物 | install 目录没有 .so |
| 5 | `package_data={'包名': ['*.so']}` | Step 4 | 同上 |
| 6 | 源码目录有 `__init__.py` | Step 2 colcon | `ModuleNotFoundError` |
| 7 | 文件名不含中文/空格/特殊字符 | Step 3-7 | dpkg-deb 拒绝 |
| 8 | `<description>` 已填写 | Step 5 control | deb Description 为空 |

---

## 五、常见踩坑

### ❌ 源码目录放错位置

```
# 错误
robot_vision/
└── lib/
    └── robot_vision/        ← CI 找不到
        └── __init__.py

# 正确
robot_vision/
├── robot_vision/            ← 和 package.xml 同级
│   └── __init__.py
└── package.xml
```

### ❌ setup.py 的 name 和 package.xml 的 name 不一致

```python
# 错误: package.xml 叫 robot_vision，setup.py 叫 robot-vision
setup(name='robot-vision', ...)
```

```python
# 正确: 两个文件用同一个名字
setup(name='robot_vision', ...)
```

### ❌ 忘配 package_data 导致 .so 丢了

```python
# 错误: colcon build 成功，但 install 目录只有 .py 没 .so
setup(packages=['robot_vision'], include_package_data=True)
# ↑ 缺了 package_data={...}

# 正确: 三件套
include_package_data=True,
package_data={'robot_vision': ['*.so']},
# + MANIFEST.in: recursive-include robot_vision *.so
```

### ❌ data_files 写了错误路径

```python
# 错误: 文件在 data/ 但只声明了通配符
data_files=[('share/robot_vision', glob.glob('data/*'))]

# 正确: 用 os.path.join 逐个声明
data_files=[
    ('share/robot_vision/data', [
        os.path.join('data', f) for f in os.listdir('data') if os.path.isfile(os.path.join('data', f))
    ]),
]
```

---

## 六、版本管理

### 首次提交

```bash
# package.xml 版本写 0.0.0
git add -A && git commit -m "init: robot_vision" && git push origin main
# CI 自动: 读到远程无此包 → bump 0.0.0 → 0.0.1
```

### 后续提交

```bash
# 改代码后直接 push，版本号由 CI 自动管
git commit -m "fix: camera timeout" && git push origin main
# CI 自动: OTA 仓库 latest=0.0.7 → bump → 0.0.8
```

### 手动指定版本

仅 CI 管理员用:
```bash
./ci_build_deb.sh robot_vision --ver 1.5.0      # 指定版本
./ci_build_deb.sh robot_vision --no-bump         # 用当前 package.xml 版本
```

---

## 七、环境变量

| 变量 | 作用 | 默认值 |
|------|------|--------|
| `ROS_DISTRO` | 目标 distro (humble/jazzy) | `humble` |
| `AUTO_BUMP` | 版本递增策略 (patch/minor/from-git/no) | `patch` |
| `BUILD_SEED` | 构建密钥 (仅 robot_utils 使用) | 首次自动生成 |

---

## 八、一分钟自检

复制你的项目根目录跑这几条:

```bash
# ① package.xml 名字一致?
grep '<name>' package.xml

# ② setup.py (Python 包)
grep -E "include_package_data|package_data" setup.py | grep True

# ③ __init__.py
test -f $(grep '<name>' package.xml | sed 's/.*<name>//;s/<\/name>//' | xargs)/__init__.py \
  && echo "OK" || echo "MISSING __init__.py"

# ④ 版本号
grep '<version>' package.xml
```

全部 OK 就可以 push，CI 会接管构建。
