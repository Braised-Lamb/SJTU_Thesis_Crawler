# 上海交通大学-学位论文系统下载器

## 问题：
[http://thesis.lib.sjtu.edu.cn/](http://thesis.lib.sjtu.edu.cn/)，该网站是上海交通大学的学位论文下载系统，收录了交大的硕士博士的论文，但是，该版权保护系统用起来很不方便，加载起来非常慢，所以该下载器实现将网页上的每一页的图片合并成一个PDF。

## 解决方案：
使用`PyMuPDF`对图片进行合并

## 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方式：

### 方式1：图形界面（推荐）

```bash
python gui_downloader.py
```

或者直接运行：
```bash
run_gui.bat
```

### 方式2：命令行界面

```bash
python downloader.py
```

## GUI界面说明

1. **搜索参数设置**
   - 选择检索方式（主题、题名、关键词、作者、院系、专业、导师、年份）
   - 选择学位类型（硕士/博士/全部）
   - 选择排序方式
   - 输入检索词和页码

2. **搜索和选择**
   - 点击"搜索论文"按钮
   - 在结果列表中勾选要下载的论文
   - 使用"全选"按钮快速选择

3. **下载**
   - 点击"下载选中论文"按钮
   - 查看下载进度和日志
   - 下载的PDF保存在`papers`文件夹中

## 文件命名格式

下载的论文文件名格式：`年份_题名_作者_导师.pdf`

## 注意事项

- 部分论文可能因保密或其他原因无法下载
- 下载过程中会创建临时文件夹`tmpjpgs`，完成后自动删除
- 已下载的论文会在状态栏显示"已存在"
 
## ToDo List
1. 如何解决`thesis.lib.sjtu.edu.cn`限制访问次数的问题
2. 引入协程，提高并发（以前试过，不过由于网站太慢了，并行就崩了），多进程的版本可以看[commit](https://github.com/olixu/SJTU_Thesis_Crawler/tree/7d712f009195f339d1cc42e6bf841db57f881052)
3. ✓ 改进交互能力 - 已添加PySide6图形界面

## 依赖库

- PySide6 - GUI界面
- PyMuPDF - PDF处理
- requests - 网络请求
- lxml - HTML解析
- beautifulsoup4 - 网页解析
- PyInquirer - 命令行交互（仅命令行模式）

## 说明（by lamb）
1. 学长写的代码在23年用起来好像有些问题，做了部分修改，配适了新的函数和网页

## 更新日志
- 2025/12/25: 添加PySide6图形界面，支持可视化交互