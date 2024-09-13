# 图像标注工具

## 概述

**图像标注工具**是一个基于PyQt5的应用程序，用于对图像进行多边形和矩形的标注。支持从文件夹加载图片，标注数据可以保存为 **JSON** 或 **XML** 格式。用户可以添加、删除、切换标注，并方便地在图像列表中进行导航。

### 主要功能
- **图片加载**：从目录中加载多个图片文件，并在查看器中显示。
- **缩放与平移**：使用鼠标滚轮进行图片缩放，按住左键拖动图片进行平移。
- **标注功能**：
  - 针对JSON文件的多边形标注。
  - 针对XML文件的矩形标注。
- **交互式界面**：
  - 添加、查看和删除标注。
  - 为每个标注分配唯一的颜色，便于区分。
  - 可以通过复选框控制标注的显示与隐藏。
- **键盘导航**：
  - 使用 `A` 或 左箭头键切换到上一张图片。
  - 使用 `D` 或 右箭头键切换到下一张图片。

## 需求

- Python 3.7+
- PyQt5
- Pillow (PIL)
- XML解析库（`xml.etree.ElementTree`）

## 安装

1. 克隆此仓库或下载代码：

    ```bash
    git clone <repository_url>
    ```

2. 安装所需的Python库：

    ```bash
    pip install PyQt5 Pillow
    ```

3. 运行应用程序：

    ```bash
    python ImageAnnotationViewer.py
    ```

## 使用说明

1. **加载图片文件**： 
   - 点击 "加载文件夹" 按钮，选择包含图片的目录（支持 `.png`, `.jpg`, `.jpeg`, `.bmp` 格式）。
   - 选中的文件夹中的图片将列在左侧，第一张图片会显示在中心区域。

2. **图片导航**：
   - 使用 "上一张图片" 和 "下一张图片" 按钮切换图片。
   - 也可以使用键盘上的 `A` 键或 `D` 键（或左右方向键）进行图片切换。

3. **添加标注**：
   - 点击 "添加标签" 按钮，输入标签名称。
   - 根据文件类型：
     - **JSON** 文件：进入多边形标注模式，点击多个点定义多边形，双击完成标注。
     - **XML** 文件：进入矩形标注模式，点击两次定义矩形的对角点。

4. **切换标注**：
   - 右侧的复选框允许切换标注的可见性。你也可以直接点击图片中的标注进行切换。

5. **删除标注**：
   - 每个标注旁边都有一个 "删除" 按钮，点击后会删除标注并更新对应的JSON或XML文件。

