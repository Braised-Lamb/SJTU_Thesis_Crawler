#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   gui_downloader.py
@Time    :   2025/12/25
@Description    :   PySide6 GUI版本的SJTU论文下载器
'''

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QMessageBox, QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont

# 导入原有的下载函数
from downloader import (
    download_main_info, paper_download, init, download_jpg, 
    merge_pdf, verify_name
)
from urllib.parse import quote
from collections import defaultdict


class DownloadThread(QThread):
    """下载线程，避免阻塞UI"""
    progress_signal = Signal(str)  # 发送进度消息
    page_progress_signal = Signal(int, int, int)  # 发送页码进度 (论文序号, 总论文数, 当前页码)
    finished_signal = Signal()  # 完成信号
    error_signal = Signal(str)  # 错误信号
    
    def __init__(self, papers):
        super().__init__()
        self.papers = papers
    
    def download_jpg_with_progress(self, url: str, jpg_dir: str, paper_idx: int, total_papers: int):
        """带进度报告的下载函数"""
        import requests
        import json
        import time
        
        headers = {
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
        }
        result = requests.Session()
        
        response = result.get(url, headers=headers, allow_redirects=False)
        if 'Location' not in response.headers:
            raise Exception("无法获取重定向地址")
        
        url = response.headers['Location']
        response = result.get(url, headers=headers, allow_redirects=False)
        if 'Location' not in response.headers:
            raise Exception("第二次重定向失败")
        
        url = response.headers['Location']
        response = result.get(url, headers=headers, allow_redirects=False)
        if 'Location' not in response.headers:
            raise Exception("第三次重定向失败")
        
        url_bix = response.headers['Location'].split('?')[1]
        url = "http://thesis.lib.sjtu.edu.cn:8443/read/jumpServlet?page=1&" + url_bix
        response = result.get(url, headers=headers, allow_redirects=False)
        urls = json.loads(response.content.decode())
        
        i = 1
        while True:
            fig_url = "http://thesis.lib.sjtu.edu.cn:8443/read/" + urls['list'][0]['src'].split('_')[0] + "_{0:05d}".format(i) + ".jpg"
            response = result.get(fig_url, headers=headers).content
            rtext = result.get(fig_url, headers=headers).text
            
            if 'HTTP状态 404 - 未找到' in result.get(fig_url, headers=headers).text:
                for t in range(10):
                    time.sleep(2)
                    rtext = result.get(fig_url, headers=headers).text
                    if 'HTTP状态 404 - 未找到' in rtext:
                        pass
                    else:
                        break
                if 'HTTP状态 404 - 未找到' in rtext:
                    break
            
            while len(response) < 2000:
                response = result.get(fig_url, headers=headers).content
            
            with open(f'./{jpg_dir}/{i}.jpg', 'wb') as f:
                f.write(response)
            
            # 发送页码进度信号
            self.page_progress_signal.emit(paper_idx, total_papers, i)
            i = i + 1
        
    def run(self):
        jpg_dir = "tmpjpgs"
        for idx, paper in enumerate(self.papers, 1):
            try:
                paper_filename = f"{paper['year']}_{paper['filename']}_{paper['author']}_{paper['mentor']}.pdf"
                
                if verify_name(paper_filename):
                    self.progress_signal.emit(f"[{idx}/{len(self.papers)}] 论文已存在: {paper['filename']}")
                    continue
                
                self.progress_signal.emit(f"[{idx}/{len(self.papers)}] 正在下载: {paper['filename']}")
                init(jpg_dir=jpg_dir)
                self.download_jpg_with_progress(paper['link'], jpg_dir, idx, len(self.papers))
                merge_pdf(paper_filename, jpg_dir=jpg_dir)
                self.progress_signal.emit(f"[{idx}/{len(self.papers)}] ✓ 完成: {paper['filename']}")
                
            except Exception as e:
                self.error_signal.emit(f"[{idx}/{len(self.papers)}] ✗ 错误: {paper['filename']} - {str(e)}")
        
        self.finished_signal.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.papers = []  # 当前页显示的论文
        self.all_papers_cache = []  # 缓存所有论文数据
        self.selected_papers = []
        self.current_page = 1
        self.total_pages = 0
        self.total_count = 0
        self.current_search_url = ""
        self.page_size = 20  # 每页显示篇数
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("SJTU 学位论文下载器")
        self.setGeometry(100, 100, 900, 700)
        
        # 主Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # 标题
        title_label = QLabel("上海交通大学学位论文下载器")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 搜索参数区域
        search_group = self.create_search_group()
        main_layout.addWidget(search_group)
        
        # 结果表格
        self.create_result_table()
        
        # 搜索结果标题行（包含排序和页码导航）
        result_header_layout = QHBoxLayout()
        result_header_layout.addWidget(QLabel("搜索结果:"))
        
        # 排序方式
        # result_header_layout.addWidget(QLabel("排序:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(['按题名字顺序排序', '按学位年度倒排序'])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)  # 连接排序变化信号
        result_header_layout.addWidget(self.sort_combo)
        
        # 添加弹性空间，让右侧内容靠右
        result_header_layout.addStretch()
        
        # 每页篇数设置（靠右）
        result_header_layout.addWidget(QLabel("每页:"))
        self.page_size_input = QLineEdit()
        self.page_size_input.setText("20")
        self.page_size_input.setMaximumWidth(50)
        self.page_size_input.setAlignment(Qt.AlignCenter)
        self.page_size_input.returnPressed.connect(self.on_page_size_changed)
        result_header_layout.addWidget(self.page_size_input)
        result_header_layout.addWidget(QLabel("篇"))
        
        # 页码导航（靠右）
        self.prev_page_btn = QPushButton("◀")
        self.prev_page_btn.setMaximumWidth(30)
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.prev_page)
        result_header_layout.addWidget(self.prev_page_btn)
        
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("1")
        self.page_input.setText("1")
        self.page_input.setMaximumWidth(50)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.returnPressed.connect(self.go_to_page)
        result_header_layout.addWidget(self.page_input)
        
        self.page_label = QLabel("/ 1")
        self.page_label.setMinimumWidth(40)
        result_header_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("▶")
        self.next_page_btn.setMaximumWidth(30)
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.next_page)
        result_header_layout.addWidget(self.next_page_btn)
        
        main_layout.addLayout(result_header_layout)
        
        main_layout.addWidget(self.result_table)
        
        # 下载按钮区域
        download_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.selected_count_label = QLabel("已选中: 0 篇")
        self.selected_count_label.setStyleSheet("QLabel { color: #2196F3; font-weight: bold; }")
        
        self.download_btn = QPushButton("📥 下载选中论文")
        self.download_btn.setStyleSheet("QPushButton { padding: 10px; font-size: 14px; background-color: #4CAF50; color: white; }")
        self.download_btn.clicked.connect(self.download_papers)
        self.download_btn.setEnabled(False)
        
        download_layout.addWidget(self.select_all_btn)
        download_layout.addWidget(self.selected_count_label)
        download_layout.addStretch()
        download_layout.addWidget(self.download_btn)
        main_layout.addLayout(download_layout)
        
        # 下载状态标签
        self.download_status_label = QLabel("")
        self.download_status_label.setStyleSheet("QLabel { color: #666; padding: 5px; }")
        main_layout.addWidget(self.download_status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)  # 显示文本
        main_layout.addWidget(self.progress_bar)
        
        # 日志输出区域（可折叠）
        log_header_layout = QHBoxLayout()
        self.log_toggle_btn = QPushButton("▼ 下载日志")
        self.log_toggle_btn.setStyleSheet("QPushButton { text-align: left; padding: 5px; background: transparent; border: none; }")
        self.log_toggle_btn.clicked.connect(self.toggle_log)
        log_header_layout.addWidget(self.log_toggle_btn)
        log_header_layout.addStretch()
        main_layout.addLayout(log_header_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setVisible(False)  # 默认隐藏
        main_layout.addWidget(self.log_text)
        
    def create_search_group(self):
        """创建搜索参数组"""
        group = QWidget()
        layout = QVBoxLayout(group)
        
        # 第一行：检索方式和学位类型
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("检索方式:"))
        self.choose_key_combo = QComboBox()
        self.choose_key_combo.addItems(['主题', '题名', '关键词', '作者', '院系', '专业', '导师', '年份'])
        row1.addWidget(self.choose_key_combo)
        
        row1.addWidget(QLabel("学位类型:"))
        self.degree_combo = QComboBox()
        self.degree_combo.addItems(['硕士及博士', '博士', '硕士'])
        row1.addWidget(self.degree_combo)
        
        layout.addLayout(row1)
        
        # 第二行：检索词和搜索按钮
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("检索词:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("请输入检索词")
        self.keyword_input.returnPressed.connect(self.search_papers)  # 支持回车搜索
        row2.addWidget(self.keyword_input)
        
        # 搜索按钮
        search_btn = QPushButton("🔍 搜索论文")
        search_btn.setStyleSheet("QPushButton { padding: 8px 20px; font-size: 14px; }")
        search_btn.clicked.connect(self.search_papers)
        row2.addWidget(search_btn)
        
        layout.addLayout(row2)
        
        return group
        
    def create_result_table(self):
        """创建结果表格"""
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(['选择', '题名', '作者', '导师', '年份', '状态'])
        
        # 设置列宽
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
    def search_papers(self):
        """搜索论文"""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "警告", "请输入检索词")
            return
        
        self.log_text.append("正在搜索...")
        
        # 构建搜索URL
        choose_key_map = {'主题':'topic', '题名':'title', '关键词':'keyword', 
                         '作者':'author', '院系':'department', '专业':'subject', 
                         '导师':'teacher', '年份':'year'}
        degree_map = {'硕士及博士':'0', '博士':'1', '硕士':'2'}
        sort_map = {'按题名字顺序排序':'1', '按学位年度倒排序':'2'}
        
        choose_key = choose_key_map[self.choose_key_combo.currentText()]
        degree = degree_map[self.degree_combo.currentText()]
        sort = sort_map[self.sort_combo.currentText()]
        
        page_str = self.page_input.text().strip() or "1"
        try:
            page = int(page_str)
            if page < 1:
                page = 1
        except ValueError:
            QMessageBox.warning(self, "警告", "页码必须是数字")
            return
        
        self.current_search_url = f"http://thesis.lib.sjtu.edu.cn/sub.asp?content={quote(keyword)}&choose_key={choose_key}&xuewei={degree}&px={sort}&page="
        self.current_page = page
        
        self.log_text.append(f"搜索URL: {self.current_search_url}{page}")
        
        try:
            # 首次搜索，获取第一页数据以获取总页数
            first_page_papers, self.total_count, self.total_pages = download_main_info(self.current_search_url, [1])
            
            # 更新页码显示
            if self.total_pages == 0:
                self.total_pages = 1
            self.page_label.setText(f"/ {self.total_pages}")
            
            if self.total_count > 0:
                self.log_text.append(f"✓ 搜索完成，共找到 {self.total_count} 条记录，共 {self.total_pages} 页")
                
                # 如果总页数较少（比如小于等于10页），一次性获取所有数据
                if self.total_pages <= 10:
                    self.log_text.append(f"正在缓存所有 {self.total_pages} 页数据...")
                    self.all_papers_cache = []
                    for p in range(1, self.total_pages + 1):
                        page_papers, _, _ = download_main_info(self.current_search_url, [p])
                        self.all_papers_cache.extend(page_papers)
                        self.log_text.append(f"已缓存第 {p}/{self.total_pages} 页")
                    self.log_text.append(f"✓ 缓存完成，共 {len(self.all_papers_cache)} 篇论文")
                    
                    # 重新计算基于自定义每页篇数的总页数
                    self.total_pages = (len(self.all_papers_cache) + self.page_size - 1) // self.page_size
                    self.page_label.setText(f"/ {self.total_pages}")
                else:
                    # 总页数较多，不缓存，每次请求
                    self.log_text.append("ℹ 由于总页数较多，将按需加载")
                    self.all_papers_cache = []  # 清空缓存
            else:
                self.log_text.append(f"✓ 搜索完成，找到 {len(first_page_papers)} 篇论文")
                self.all_papers_cache = []  # 清空缓存
            
            # 显示当前页
            if page == 1 or not self.all_papers_cache:
                self.papers = first_page_papers
            else:
                # 从缓存中获取
                start_idx = (page - 1) * self.page_size
                end_idx = min(start_idx + self.page_size, len(self.all_papers_cache))
                self.papers = self.all_papers_cache[start_idx:end_idx]
            
            self.page_input.setText(str(self.current_page))
            self.prev_page_btn.setEnabled(self.current_page > 1)
            self.next_page_btn.setEnabled(self.current_page < self.total_pages)
            
            self.display_papers()
            
            if self.papers:
                self.download_btn.setEnabled(True)
        except Exception as e:
            self.log_text.append(f"✗ 搜索失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"搜索失败: {str(e)}")
            
    def display_papers(self):
        """显示搜索结果"""
        self.result_table.setRowCount(len(self.papers))
        
        for row, paper in enumerate(self.papers):
            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(False)  # 默认不选中
            checkbox.stateChanged.connect(self.update_selected_count)  # 连接信号
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(row, 0, checkbox_widget)
            
            # 其他信息
            self.result_table.setItem(row, 1, QTableWidgetItem(paper['filename']))
            self.result_table.setItem(row, 2, QTableWidgetItem(paper['author']))
            self.result_table.setItem(row, 3, QTableWidgetItem(paper['mentor']))
            self.result_table.setItem(row, 4, QTableWidgetItem(paper['year']))
            
            # 检查文件是否已存在
            paper_filename = f"{paper['year']}_{paper['filename']}_{paper['author']}_{paper['mentor']}.pdf"
            status = "已存在" if verify_name(paper_filename) else "未下载"
            status_item = QTableWidgetItem(status)
            if status == "已存在":
                status_item.setForeground(Qt.green)
            self.result_table.setItem(row, 5, status_item)
        
        # 更新选中计数
        self.update_selected_count()
            
    def select_all(self):
        """全选/取消全选"""
        if self.select_all_btn.text() == "全选":
            for row in range(self.result_table.rowCount()):
                checkbox_widget = self.result_table.cellWidget(row, 0)
                checkbox = checkbox_widget.findChild(QCheckBox)
                checkbox.setChecked(True)
            self.select_all_btn.setText("取消全选")
        else:
            for row in range(self.result_table.rowCount()):
                checkbox_widget = self.result_table.cellWidget(row, 0)
                checkbox = checkbox_widget.findChild(QCheckBox)
                checkbox.setChecked(False)
            self.select_all_btn.setText("全选")
        self.update_selected_count()
            
    def download_papers(self):
        """下载选中的论文"""
        selected_papers = []
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox.isChecked():
                selected_papers.append(self.papers[row])
        
        if not selected_papers:
            QMessageBox.warning(self, "警告", "请至少选择一篇论文")
            return
        
        reply = QMessageBox.question(
            self, '确认', 
            f'确认下载 {len(selected_papers)} 篇论文吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        self.download_btn.setEnabled(False)
        self.log_text.append(f"\n开始下载 {len(selected_papers)} 篇论文...")
        self.download_status_label.setText(f"准备下载 {len(selected_papers)} 篇论文...")
        self.download_status_label.setStyleSheet("QLabel { color: #2196F3; padding: 5px; }")
        
        # 创建并启动下载线程
        self.download_thread = DownloadThread(selected_papers)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.page_progress_signal.connect(self.update_page_progress)
        self.download_thread.error_signal.connect(self.update_error)
        self.download_thread.finished_signal.connect(self.download_finished)
        
        self.progress_bar.setMaximum(len(selected_papers))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0/%d - 0%%" % len(selected_papers))
        self.download_thread.start()
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 1 and self.current_search_url:
            self.current_page -= 1
            self.page_input.setText(str(self.current_page))
            self.load_page()
    
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages and self.current_search_url:
            self.current_page += 1
            self.page_input.setText(str(self.current_page))
            self.load_page()
    
    def go_to_page(self):
        """跳转到指定页"""
        if not self.current_search_url:
            QMessageBox.warning(self, "警告", "请先执行搜索")
            return
        
        page_str = self.page_input.text().strip()
        try:
            page = int(page_str)
            if page < 1 or page > self.total_pages:
                QMessageBox.warning(self, "警告", f"页码必须在 1 到 {self.total_pages} 之间")
                self.page_input.setText(str(self.current_page))
                return
            self.current_page = page
            self.load_page()
        except ValueError:
            QMessageBox.warning(self, "警告", "页码必须是数字")
            self.page_input.setText(str(self.current_page))
    
    def on_sort_changed(self):
        """排序方式变化时重新搜索"""
        if self.current_search_url:
            # 已经有搜索结果，重新搜索
            self.log_text.append("排序方式已更改，重新搜索...")
            self.search_papers()
    
    def on_page_size_changed(self):
        """每页篇数变化时重新分页"""
        page_size_str = self.page_size_input.text().strip()
        try:
            new_page_size = int(page_size_str)
            if new_page_size < 1:
                QMessageBox.warning(self, "警告", "每页篇数必须大于0")
                self.page_size_input.setText(str(self.page_size))
                return
            if new_page_size > 100:
                QMessageBox.warning(self, "警告", "每页篇数不能超过100")
                self.page_size_input.setText(str(self.page_size))
                return
            
            # 如果没有缓存，仅更新配置值
            if not self.all_papers_cache:
                self.page_size = new_page_size
                self.log_text.append(f"每页篇数已设置为 {self.page_size}（将在下次搜索时生效）")
                return
            
            self.page_size = new_page_size
            
            # 重新计算总页数
            self.total_pages = (len(self.all_papers_cache) + self.page_size - 1) // self.page_size
            if self.total_pages == 0:
                self.total_pages = 1
            
            # 调整当前页码，确保不超出范围
            if self.current_page > self.total_pages:
                self.current_page = self.total_pages
            
            # 更新页码显示
            self.page_label.setText(f"/ {self.total_pages}")
            self.page_input.setText(str(self.current_page))
            
            # 更新按钮状态
            self.prev_page_btn.setEnabled(self.current_page > 1)
            self.next_page_btn.setEnabled(self.current_page < self.total_pages)
            
            # 重新加载当前页
            self.load_page()
            
            self.log_text.append(f"每页篇数已调整为 {self.page_size}，重新分页，第 {self.current_page} 页已刷新")
        except ValueError:
            QMessageBox.warning(self, "警告", "每页篇数必须是数字")
            self.page_size_input.setText(str(self.page_size))
    
    def load_page(self):
        """加载指定页的内容"""
        try:
            # 如果有缓存，从缓存中读取
            if self.all_papers_cache:
                self.log_text.append(f"从缓存加载第 {self.current_page} 页...")
                start_idx = (self.current_page - 1) * self.page_size
                end_idx = min(start_idx + self.page_size, len(self.all_papers_cache))
                self.papers = self.all_papers_cache[start_idx:end_idx]
            else:
                # 没有缓存，从服务器请求（网站固定每页20条）
                self.log_text.append(f"正在加载第 {self.current_page} 页...")
                self.papers, _, _ = download_main_info(self.current_search_url, [self.current_page])
            
            # 更新页码按钮状态
            self.prev_page_btn.setEnabled(self.current_page > 1)
            self.next_page_btn.setEnabled(self.current_page < self.total_pages)
            
            self.display_papers()
            self.log_text.append(f"✓ 第 {self.current_page} 页加载完成，显示 {len(self.papers)} 篇论文")
            
            if self.papers:
                self.download_btn.setEnabled(True)
        except Exception as e:
            self.log_text.append(f"✗ 加载失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载页面失败: {str(e)}")
    
    def update_selected_count(self):
        """更新选中的论文数量"""
        count = 0
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    count += 1
        self.selected_count_label.setText(f"已选中: {count} 篇")
    
    def toggle_log(self):
        """切换日志显示/隐藏"""
        if self.log_text.isVisible():
            self.log_text.setVisible(False)
            self.log_toggle_btn.setText("▶ 下载日志")
        else:
            self.log_text.setVisible(True)
            self.log_toggle_btn.setText("▼ 下载日志")
        
    @Slot(str)
    def update_progress(self, message):
        """更新进度"""
        # 不自动展开日志，只记录
        self.log_text.append(message)
        
        # 更新状态标签
        self.download_status_label.setText(message)
        self.download_status_label.setStyleSheet("QLabel { color: #666; padding: 5px; }")
        
        current = self.progress_bar.value()
        if "完成" in message or "已存在" in message:
            self.progress_bar.setValue(current + 1)
            # 更新进度条文本
            self.progress_bar.setFormat(f"{current + 1}/{self.progress_bar.maximum()} - {int((current + 1) / self.progress_bar.maximum() * 100)}%")
    
    @Slot(int, int, int)
    def update_page_progress(self, paper_idx, total_papers, page_num):
        """更新页码进度"""
        status_text = f"[第{paper_idx}篇/共{total_papers}篇] 正在下载第 {page_num} 页"
        self.download_status_label.setText(status_text)
        self.download_status_label.setStyleSheet("QLabel { color: #2196F3; padding: 5px; }")
    
    @Slot(str)
    def update_error(self, message):
        """更新错误信息"""
        # 不自动展开日志，只记录
        self.log_text.append(message)
        
        # 更新状态标签
        self.download_status_label.setText(message)
        self.download_status_label.setStyleSheet("QLabel { color: #f44336; padding: 5px; }")
        
        current = self.progress_bar.value()
        self.progress_bar.setValue(current + 1)
        # 更新进度条文本
        self.progress_bar.setFormat(f"{current + 1}/{self.progress_bar.maximum()} - {int((current + 1) / self.progress_bar.maximum() * 100)}%")
        
    @Slot()
    def download_finished(self):
        """下载完成"""
        self.log_text.append("\n所有下载任务完成！")
        self.download_status_label.setText("✓ 所有论文下载完成！")
        self.download_status_label.setStyleSheet("QLabel { color: #4CAF50; padding: 5px; font-weight: bold; }")
        self.download_btn.setEnabled(True)
        QMessageBox.information(self, "完成", "所有论文下载完成！")
        # 刷新状态
        self.display_papers()


def main():
    app = QApplication(sys.argv)
    
    # 使用Fusion样式确保跨平台一致性
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
