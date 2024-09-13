from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsTextItem, QVBoxLayout, QHBoxLayout, \
    QListWidget, QPushButton, QGraphicsScene, QGraphicsView, QScrollArea, QWidget, QInputDialog, QApplication, \
    QMessageBox, QCheckBox, QFileDialog, QSplitter, QLabel, QGraphicsEllipseItem
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPolygonF, QBrush
from PyQt5.QtCore import Qt, QPointF, QRectF
import sys
from PIL import Image
import os
import json
import xml.etree.ElementTree as ET

def resize_image(image, max_width, max_height):
    w_ratio = max_width / image.width
    h_ratio = max_height / image.height
    ratio = min(w_ratio, h_ratio)
    new_size = (int(image.width * ratio), int(image.height * ratio))
    return image.resize(new_size, Image.Resampling.LANCZOS), ratio
def point_in_polygon(point, polygon):
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside
class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent_viewer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.15
        self.is_annotation_mode = False  # 标注模式标识
        self.drawing_points = []
        self.parent_viewer = parent_viewer
        self.annotation_type = None

    def wheelEvent(self, event):
        """使用鼠标滚轮缩放图片和标注"""
        zoom_in = event.angleDelta().y() > 0  # 判断滚轮方向
        if zoom_in:
            self.scale(self.scale_factor, self.scale_factor)  # 放大
        else:
            self.scale(1 / self.scale_factor, 1 / self.scale_factor)  # 缩小

    def mousePressEvent(self, event):
        """根据标注模式或正常模式处理鼠标点击事件"""
        scene_pos = self.mapToScene(event.pos())

        if self.is_annotation_mode:
            # 处于标注模式，根据类型绘制多边形或矩形
            if self.annotation_type == 'polygon':
                self.drawing_points.append((scene_pos.x(), scene_pos.y()))
                # 绘制当前点击的点
                self.parent_viewer.graphics_scene.addEllipse(scene_pos.x() - 2, scene_pos.y() - 2, 4, 4,
                                                             QPen(QColor('blue')),
                                                             QBrush(QColor('blue')))
            elif self.annotation_type == 'rectangle':
                self.drawing_points.append((scene_pos.x(), scene_pos.y()))
                if len(self.drawing_points) == 2:
                    # 完成矩形绘制
                    self.setCursor(Qt.ArrowCursor)  # 恢复鼠标样式
                    self.parent_viewer.save_rectangle_to_xml(self.parent_viewer.last_label_name, self.drawing_points)
                    self.exit_annotation_mode()
        else:
            # 正常模式下处理点击事件
            if hasattr(self.parent_viewer, 'handle_click_on_annotation'):
                self.parent_viewer.handle_click_on_annotation(scene_pos)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击事件用于完成多边形绘制"""
        if self.is_annotation_mode and self.annotation_type == 'polygon' and len(self.drawing_points) > 2:
            # 双击完成多边形绘制
            self.setCursor(Qt.ArrowCursor)  # 恢复鼠标样式
            self.parent_viewer.save_polygon_to_json(self.parent_viewer.last_label_name, self.drawing_points)
            self.exit_annotation_mode()

        super().mouseDoubleClickEvent(event)

    def enter_annotation_mode(self, annotation_type):
        """进入标注模式"""
        self.is_annotation_mode = True
        self.annotation_type = annotation_type
        self.drawing_points = []
        self.setCursor(Qt.CrossCursor)

    def exit_annotation_mode(self):
        """退出标注模式"""
        self.is_annotation_mode = False
        self.annotation_type = None
        self.drawing_points = []
        self.setCursor(Qt.ArrowCursor)


class ImageAnnotationViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skysys")
        self.setGeometry(100, 100, 1200, 800)

        # 设置颜色映射表，用于不同标签类型的颜色
        self.label_color_map = {}
        self.default_colors = [QColor("red"), QColor("blue"), QColor("green"), QColor("yellow"),
                               QColor("purple"), QColor("orange"), QColor("cyan"), QColor("magenta")]
        self.color_index = 0  # 用于分配颜色的索引
        self.img_display = None
        self.annotations = []
        self.current_file_path = None
        self.current_annotation_path = None
        self.image_ratio = 1
        self.x_offset = 0
        self.y_offset = 0
        self.image_files = []
        self.current_index = 0
        self.annotation_checkboxes = {}  # 保存复选框
        self.last_label_name = "Default Label"  # 默认的标签名称

        # 设置主布局
        main_layout = QVBoxLayout(self)

        # 控制按钮布局
        control_layout = QHBoxLayout()
        self.load_button = QPushButton('加载文件夹')
        self.load_button.clicked.connect(self.load_files)
        control_layout.addWidget(self.load_button)
        main_layout.addLayout(control_layout)

        # 使用 QSplitter 实现拖动调整大小的功能
        splitter = QSplitter(Qt.Horizontal)  # 创建水平分割线

        # 左侧：图片文件列表
        left_layout = QVBoxLayout()

        # 新增一个标签显示当前图片是第几张，总共有几张
        self.image_count_label = QLabel("当前第 0 张，共 0 张")
        left_layout.addWidget(self.image_count_label)

        # 左侧：图片文件列表
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self.on_select_file)  # 添加行变化信号的连接
        left_layout.addWidget(self.file_list)

        # 创建一个 QWidget 来包含左侧布局，并将其添加到 splitter
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # 中间：图片显示区
        self.graphics_view = ZoomableGraphicsView(self)
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        splitter.addWidget(self.graphics_view)  # 将图片显示区域添加到splitter

        # 右侧：标签选择框
        self.label_frame = QScrollArea()
        self.label_frame.setWidgetResizable(True)
        self.label_frame_content = QWidget()
        self.label_frame_layout = QVBoxLayout(self.label_frame_content)
        self.label_frame.setWidget(self.label_frame_content)
        splitter.addWidget(self.label_frame)  # 将标签选择框添加到splitter

        splitter.setSizes([200, 800, 200])

        main_layout.addWidget(splitter)

        # 控制按钮布局
        button_layout = QHBoxLayout()
        self.prev_button = QPushButton('上一张图片')
        self.prev_button.clicked.connect(self.prev_image)
        button_layout.addWidget(self.prev_button)

        self.add_label_button = QPushButton('添加标签')
        self.add_label_button.clicked.connect(self.add_label)
        button_layout.addWidget(self.add_label_button)

        self.next_button = QPushButton('下一张图片')
        self.next_button.clicked.connect(self.next_image)
        button_layout.addWidget(self.next_button)

        main_layout.addLayout(button_layout)

    def load_files(self):
        """加载图片文件目录"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.image_files = [os.path.join(directory, f) for f in os.listdir(directory)
                                if f.endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
            self.file_list.clear()
            for file in self.image_files:
                self.file_list.addItem(os.path.basename(file))
            self.current_index = 0
            if self.image_files:
                self.update_image_display(self.image_files[self.current_index])
            # 更新图片计数标签
            self.update_image_count_label()

    def update_image_display(self, file_path):
        """更新图片显示和标注"""
        self.current_file_path = file_path
        self.file_list.setCurrentRow(self.current_index)
        self.update_annotations_display(file_path)

    def prev_image(self):
        """显示前一张图片"""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_image_display(self.image_files[self.current_index])
            # 更新图片计数标签
            self.update_image_count_label()

    def next_image(self):
        """显示下一张图片"""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.update_image_display(self.image_files[self.current_index])
            # 更新图片计数标签
            self.update_image_count_label()

    def update_image_count_label(self):
        """更新图片计数标签"""
        total_images = len(self.image_files)
        current_image = self.current_index + 1 if self.image_files else 0
        self.image_count_label.setText(f"当前第 {current_image} 张，共 {total_images} 张")

    def keyPressEvent(self, event):
        """捕获键盘事件，用于切换图片"""
        if event.key() == Qt.Key_A or event.key() == Qt.Key_Left:
            self.prev_image()  # 按下A键或左箭头键，显示上一张图片
        elif event.key() == Qt.Key_D or event.key() == Qt.Key_Right:
            self.next_image()  # 按下D键或右箭头键，显示下一张图片
    def on_select_file(self, index):
        """当用户选择文件时，显示对应的图片和标注"""
        if index >= 0 and index < len(self.image_files):
            self.current_index = index
            self.update_image_display(self.image_files[index])
            # 更新图片计数标签
            self.update_image_count_label()

    def update_annotations_display(self, file_path):
        """更新图片和标注的显示"""
        base_path = file_path.rsplit('.', 1)[0]
        json_path = base_path + '.json'
        xml_path = base_path + '.xml'

        if os.path.exists(json_path):
            self.current_annotation_path = json_path
        elif os.path.exists(xml_path):
            self.current_annotation_path = xml_path
        else:
            QMessageBox.critical(self, "File Not Found", "No corresponding JSON or XML annotation file found.")
            return

        try:
            image = Image.open(file_path)
            resized_image, ratio = resize_image(image, 800, 600)
            self.image_ratio = ratio
            self.x_offset = (800 - resized_image.width) / 2
            self.y_offset = (450 - resized_image.height) / 2  # 调整为450，图片和标注更匹配

            self.annotations = self.parse_annotation(self.current_annotation_path, ratio, self.x_offset, self.y_offset)

            # 在QGraphicsScene中显示图像
            qimage = QImage(resized_image.tobytes(), resized_image.width, resized_image.height, resized_image.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            self.graphics_scene.clear()  # 清空之前的图像和标注
            self.graphics_scene.addPixmap(pixmap)
            self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(), Qt.KeepAspectRatio)

            # 更新标注显示
            self.update_annotation_checkboxes()
            self.update_canvas_annotations()

        except FileNotFoundError as e:
            QMessageBox.critical(self, "File Not Found", f"Could not find the file: {e.filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

        except FileNotFoundError as e:
            QMessageBox.critical(self, "File Not Found", f"Could not find the file: {e.filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def get_label_color(self, label):
        """根据标签名称获取颜色，如果没有分配颜色，则分配新的颜色"""
        if label not in self.label_color_map:
            # 如果标签还没有分配颜色，分配一个新的颜色
            color = self.default_colors[self.color_index % len(self.default_colors)]
            self.label_color_map[label] = color
            self.color_index += 1
        return self.label_color_map[label]
    def parse_annotation(self, annotation_path, ratio, x_offset, y_offset):
        annotations = []
        if annotation_path.endswith('.json'):
            with open(annotation_path, 'r') as file:
                data = json.load(file)
                for i, shape in enumerate(data['shapes']):
                    points = shape['points']
                    label = shape['label']
                    scaled_points = [(x * ratio + x_offset, y * ratio + y_offset) for x, y in points]
                    annotations.append({'type': 'polygon', 'points': scaled_points, 'label': label, 'index': i})
        elif annotation_path.endswith('.xml'):
            tree = ET.parse(annotation_path)
            root = tree.getroot()
            for i, obj in enumerate(root.findall('object')):
                label = obj.find('name').text
                bndbox = obj.find('bndbox')
                xmin = int(float(bndbox.find('xmin').text) * ratio + x_offset)
                ymin = int(float(bndbox.find('ymin').text) * ratio + y_offset)
                xmax = int(float(bndbox.find('xmax').text) * ratio + x_offset)
                ymax = int(float(bndbox.find('ymax').text) * ratio + y_offset)
                points = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
                annotations.append({'type': 'rectangle', 'points': points, 'label': label, 'index': i})
        return annotations

    def update_annotation_checkboxes(self):
        """更新标签复选框，并为每个标签添加删除按钮"""
        # 首先清空之前的复选框和按钮
        for i in reversed(range(self.label_frame_layout.count())):
            widget = self.label_frame_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.annotation_checkboxes.clear()

        for annotation in self.annotations:
            # 创建复选框
            checkbox = QCheckBox(f"{annotation['label']} #{annotation['index']}")
            checkbox.setFixedHeight(20)  # 固定高度，紧凑排列
            checkbox.setChecked(True)  # 默认显示所有标签
            checkbox.stateChanged.connect(self.update_canvas_annotations)
            self.annotation_checkboxes[annotation['index']] = checkbox

            # 创建删除按钮，确保每个按钮对应正确的标注
            delete_button = QPushButton("删除")
            delete_button.setFixedHeight(20)  # 固定高度，紧凑排列
            delete_button.clicked.connect(lambda _, index=annotation['index']: self.confirm_delete_annotation(index))

            # 将复选框和删除按钮加入标签选择框，使用垂直布局
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setSpacing(5)  # 控制组件之间的间距
            layout.addWidget(checkbox)
            layout.addWidget(delete_button)  # 删除按钮放在标签名称下方
            self.label_frame_layout.addWidget(container)

        self.label_frame.setWidget(self.label_frame_content)

    def confirm_delete_annotation(self, index):
        """弹出确认对话框，确认是否删除标签"""
        try:
            # 检查索引是否有效，避免越界错误
            if 0 <= index < len(self.annotations):
                annotation_label = self.annotations[index]['label']
                reply = QMessageBox.question(self, "确认删除", f"确定要删除标签 '{annotation_label}' 吗？",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.delete_annotation(index)
            else:
                raise IndexError("标注索引无效！")
        except IndexError as e:
            print(f"Error: {str(e)}")

    def update_canvas_annotations(self):
        """根据注释内容在图片上绘制多边形和矩形，并根据复选框状态控制显示"""
        # 清除现有的标注
        for item in self.graphics_scene.items():
            if isinstance(item, (QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem)):
                self.graphics_scene.removeItem(item)

        # 遍历标注并绘制
        for annotation in self.annotations:
            if self.annotation_checkboxes[annotation['index']].isChecked():
                # 获取对应标签的颜色
                color = self.get_label_color(annotation['label'])

                if annotation['type'] == 'polygon':
                    self.draw_polygon_annotation(annotation, color)
                elif annotation['type'] == 'rectangle':
                    self.draw_rectangle_annotation(annotation, color)

    def draw_polygon_annotation(self, annotation, color):
        """绘制多边形标注，使用给定的颜色，并在多边形外显示标签"""
        polygon = QPolygonF()
        for point in annotation['points']:
            polygon.append(QPointF(point[0], point[1]))  # 将标注的点加入多边形
        polygon_item = QGraphicsPolygonItem(polygon)
        polygon_item.setPen(QPen(color, 2))  # 设置多边形线条颜色和宽度
        self.graphics_scene.addItem(polygon_item)

        # 绘制顶点标记，使用相同的颜色
        for point in annotation['points']:
            ellipse = QGraphicsEllipseItem(point[0] - 2, point[1] - 2, 4, 4)  # 小圆标记顶点
            ellipse.setBrush(QBrush(color))  # 设置顶点填充颜色与线条相同
            ellipse.setPen(QPen(color))  # 设置边框颜色与线条相同
            self.graphics_scene.addItem(ellipse)

        # 在多边形的第一个点附近显示标签名称
        label_text = f"{annotation['label']} #{annotation['index']}"
        label = QGraphicsTextItem(label_text)
        label.setDefaultTextColor(color)
        # 设置标签的位置，偏移以避免与标注重叠
        first_point = annotation['points'][0]
        label_offset_x, label_offset_y = 10, -20  # 向右下偏移标签显示位置
        label.setPos(first_point[0] + label_offset_x, first_point[1] + label_offset_y)

        self.graphics_scene.addItem(label)

    def draw_rectangle_annotation(self, annotation, color):
        """绘制矩形标注，使用给定的颜色，并在矩形的外部显示标签"""
        x1, y1 = annotation['points'][0]
        x2, y2 = annotation['points'][2]  # 矩形对角线的两个点
        rect = QRectF(QPointF(x1, y1), QPointF(x2, y2))  # 创建矩形
        rect_item = QGraphicsRectItem(rect)
        rect_item.setPen(QPen(color, 2))  # 设置矩形边框颜色和宽度
        self.graphics_scene.addItem(rect_item)

        # 在矩形的右上角显示标签名称，并偏移一些以防重叠
        label_text = f"{annotation['label']} #{annotation['index']}"
        label = QGraphicsTextItem(label_text)
        label.setDefaultTextColor(color)

        label_offset_x, label_offset_y = 10, -10  # 偏移标签显示位置
        label.setPos(x1 + label_offset_x, y1 + label_offset_y)

        self.graphics_scene.addItem(label)

    def handle_click_on_annotation(self, scene_pos):
        """处理用户点击的标注区域，切换标签显示状态并同步复选框"""
        for annotation in self.annotations:
            # 检查点击位置是否在多边形内部
            if annotation['type'] == 'polygon':
                polygon = QPolygonF([QPointF(point[0], point[1]) for point in annotation['points']])
                if polygon.containsPoint(scene_pos, Qt.OddEvenFill):
                    self.toggle_annotation_display(annotation['index'])
                    break
            # 检查点击位置是否在矩形内部
            elif annotation['type'] == 'rectangle':
                x1, y1 = annotation['points'][0]
                x2, y2 = annotation['points'][2]
                rect = QRectF(QPointF(x1, y1), QPointF(x2, y2))
                if rect.contains(scene_pos):
                    self.toggle_annotation_display(annotation['index'])
                    break

    def toggle_annotation_display(self, index):
        """切换标注的显示状态，并更新复选框的勾选状态"""
        checkbox = self.annotation_checkboxes[index]
        checkbox.setChecked(not checkbox.isChecked())  # 切换复选框状态，更新显示
        self.update_canvas_annotations()  # 重新更新画布标注

    def delete_annotation(self, index):
        """根据标注的 index 来删除标注，而不是依赖列表索引"""
        try:
            # 查找要删除的标注
            annotation_to_delete = next((a for a in self.annotations if a['index'] == index), None)
            if annotation_to_delete is None:
                raise IndexError("标注索引无效！")

            # 从内存中删除标注
            self.annotations = [a for a in self.annotations if a['index'] != index]

            # 删除文件中的标注
            if self.current_annotation_path.endswith('.json'):
                with open(self.current_annotation_path, 'r+') as file:
                    data = json.load(file)
                    data['shapes'] = [s for i, s in enumerate(data['shapes']) if i != index]
                    file.seek(0)
                    json.dump(data, file, indent=4)
                    file.truncate()

            elif self.current_annotation_path.endswith('.xml'):
                tree = ET.parse(self.current_annotation_path)
                root = tree.getroot()
                objects = root.findall('object')
                object_to_delete = objects[index]
                root.remove(object_to_delete)
                tree.write(self.current_annotation_path)

            # 重新对 annotations 进行索引编号，确保索引连续有效
            for i, annotation in enumerate(self.annotations):
                annotation['index'] = i  # 重新编号索引

            # 更新UI，重新生成复选框并同步显示
            self.update_annotation_checkboxes()
            self.update_canvas_annotations()

        except IndexError as e:
            print(f"Error: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def add_label(self):
        """添加新标注，支持 JSON 文件的多边形添加，XML 文件的矩形添加"""
        label_name, ok = QInputDialog.getText(self, '输入标签名称', '请输入标签名称:', text=self.last_label_name)
        if not ok or not label_name:
            return

        self.last_label_name = label_name

        if self.current_annotation_path.endswith('.json'):
            # 进入多边形标注模式
            self.graphics_view.enter_annotation_mode('polygon')
        elif self.current_annotation_path.endswith('.xml'):
            # 进入矩形标注模式
            self.graphics_view.enter_annotation_mode('rectangle')

    def add_polygon_annotation(self, label_name):
        """添加多边形标注（适用于 JSON 文件）"""
        self.drawing_points = []  # 清空当前的绘制点
        self.graphics_view.setCursor(Qt.CrossCursor)  # 更改鼠标为十字光标，表示处于绘制状态

        def handle_click(event):
            scene_pos = self.graphics_view.mapToScene(event.pos())
            self.drawing_points.append((scene_pos.x(), scene_pos.y()))
            # 绘制当前点击的点
            self.graphics_scene.addEllipse(scene_pos.x() - 2, scene_pos.y() - 2, 4, 4, QPen(QColor('blue')),
                                           QBrush(QColor('blue')))

        def handle_double_click(event):
            # 双击完成多边形的绘制，保存到文件并解除绑定事件
            if len(self.drawing_points) > 2:
                self.graphics_view.setCursor(Qt.ArrowCursor)  # 恢复鼠标样式
                self.graphics_view.mousePressEvent = None
                self.graphics_view.mouseDoubleClickEvent = None
                self.save_polygon_to_json(label_name, self.drawing_points)

        # 绑定鼠标点击事件和双击事件
        self.graphics_view.mousePressEvent = handle_click
        self.graphics_view.mouseDoubleClickEvent = handle_double_click

    def add_rectangle_annotation(self, label_name):
        """添加矩形标注（适用于 XML 文件）"""
        self.drawing_points = []  # 清空当前的绘制点
        self.graphics_view.setCursor(Qt.CrossCursor)  # 更改鼠标为十字光标

        def handle_click(event):
            scene_pos = self.graphics_view.mapToScene(event.pos())
            self.drawing_points.append((scene_pos.x(), scene_pos.y()))
            if len(self.drawing_points) == 2:
                # 完成矩形的绘制
                self.graphics_view.setCursor(Qt.ArrowCursor)  # 恢复鼠标样式
                self.graphics_view.mousePressEvent = None
                self.save_rectangle_to_xml(label_name, self.drawing_points)

        # 绑定单击事件，添加矩形的两个对角点
        self.graphics_view.mousePressEvent = handle_click

    def convert_to_original_coordinates(self, points):
        """将显示在屏幕上的坐标转换为原始图像的坐标"""
        original_points = []
        for x, y in points:
            original_x = (x - self.x_offset) / self.image_ratio
            original_y = (y - self.y_offset) / self.image_ratio
            original_points.append((original_x, original_y))
        return original_points

    def save_polygon_to_json(self, label_name, points):
        """保存多边形标注到 JSON 文件"""
        # 将屏幕坐标转换为原始图像的坐标
        original_points = self.convert_to_original_coordinates(points)
        with open(self.current_annotation_path, 'r+') as file:
            data = json.load(file)
            # 添加新的多边形
            new_shape = {'label': label_name, 'points': original_points, 'shape_type': 'polygon'}
            data['shapes'].append(new_shape)
            file.seek(0)
            json.dump(data, file, indent=4)
            file.truncate()

        # 更新UI
        self.annotations.append(
            {'type': 'polygon', 'points': points, 'label': label_name, 'index': len(self.annotations)})
        self.update_annotation_checkboxes()
        self.update_canvas_annotations()

    def save_rectangle_to_xml(self, label_name, points):
        """保存矩形标注到 XML 文件"""
        # 将屏幕坐标转换为原始图像的坐标
        original_points = self.convert_to_original_coordinates(points)
        x1, y1 = original_points[0]
        x1_1, y1_1 = points[0]
        x2, y2 = original_points[1]
        x2_2, y2_2 = points[1]
        tree = ET.parse(self.current_annotation_path)
        root = tree.getroot()

        # 创建新的 object 标签
        obj = ET.Element('object')
        ET.SubElement(obj, 'name').text = label_name
        bndbox = ET.SubElement(obj, 'bndbox')
        ET.SubElement(bndbox, 'xmin').text = str(int(min(x1, x2)))
        ET.SubElement(bndbox, 'ymin').text = str(int(min(y1, y2)))
        ET.SubElement(bndbox, 'xmax').text = str(int(max(x1, x2)))
        ET.SubElement(bndbox, 'ymax').text = str(int(max(y1, y2)))
        root.append(obj)

        tree.write(self.current_annotation_path)
        # 更新内存中的标注并重新显示
        points = [(int(min(x1_1, x2_2)), int(min(y1_1, y2_2))), (int(max(x1_1, x2_2)), int(min(y1_1, y2_2))),
                  (int(max(x1_1, x2_2)), int(max(y1_1, y2_2))), (int(min(x1_1, x2_2)), int(max(y1_1, y2_2)))]
        self.annotations.append(
            {'type': 'rectangle', 'points': points, 'label': label_name, 'index': len(self.annotations)})
        self.update_annotation_checkboxes()
        self.update_canvas_annotations()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageAnnotationViewer()
    viewer.show()
    sys.exit(app.exec_())