#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   downloader.py
@Time    :   2021/06/27 10:24:10
@Author  :   olixu 
@Version :   1.0
@Contact :   273601727@qq.com
@WebSite    :   https://blog.oliverxu.cn

@Modified by    :   lamb
@Modified time  :   2025/12/25 09:54:25
@Description    :   modified code with PyInquirer for better user interaction
'''
# here put the import lib
from __future__ import print_function, unicode_literals
import os
import sys
import time
import random
import json
import shutil
from collections import defaultdict
from urllib.parse import quote
import requests
from lxml import etree
import pymupdf

# PyInquirer is only needed for CLI mode, make it optional for GUI packaging
try:
    from PyInquirer import style_from_dict, Token, prompt
    PYINQUIRER_AVAILABLE = True
except ImportError:
    PYINQUIRER_AVAILABLE = False
    style_from_dict = Token = prompt = None

def main():
    """
    下载学位论文入口程序：

    调用方式：python downloader.py --pages '1-2' --major '计算机'
    """
    answers = search_arguments()
    info_url, pages = arguments_extract(answers)
    papers, total_count, total_pages = download_main_info(info_url, pages)
    if total_count > 0:
        print(f"共找到 {total_count} 条记录，共 {total_pages} 页")
    will_download = confirmation(papers)['confirmation']
    if will_download:
        paper_download(papers)
    else:
        print('Bye!')

def paper_download(papers):
    jpg_dir = "tmpjpgs"
    for paper in papers:
        print(100*'@')
        paper_filename = paper['year'] + '_' + paper['filename'] + '_' + paper['author'] + '_' + paper['mentor'] + '.pdf'
        if verify_name(paper_filename):
            print("论文{}已经存在".format(paper_filename))
            continue
        print("正在下载论文：", paper['filename'])
        init(jpg_dir=jpg_dir)
        try:
            download_jpg(paper['link'], jpg_dir=jpg_dir)
            merge_pdf(paper_filename, jpg_dir=jpg_dir)
        except Exception as e:
            print(e)

def search_arguments():
    if not PYINQUIRER_AVAILABLE:
        raise ImportError("PyInquirer is required for CLI mode. Install it with: pip install PyInquirer")
    
    style = style_from_dict({
                Token.Separator: '#cc5454',
                Token.QuestionMark: '#673ab7 bold',
                Token.Selected: '#cc5454',  # default
                Token.Pointer: '#673ab7 bold',
                Token.Instruction: '',  # default
                Token.Answer: '#f44336 bold',
                Token.Question: '',
                })

    questions = [
        {
            'type': 'list',
            'message': '请选择检索方式',
            'name': 'choose_key',
            'choices': [
                '主题',
                '题名',
                '关键词',
                '作者',
                '院系',
                '专业',
                '导师',
                '年份'

            ]
        },
        {
            'type': 'list',
            'message': '请选择检索硕士或博士论文',
            'name': 'xuewei',
            'choices': [
                '硕士',
                '博士',
                '硕士及博士'
            ]
        },
        {
            'type': 'list',
            'message': '请选择排序方式',
            'name': 'px',
            'choices': [
                '按题名字顺序排序',
                '按学位年度倒排序'
            ]
        },
        {
            'type': 'input',
            'name': 'content',
            'message': '请输入你的检索词'
        },
        {
            'type': 'input',
            'name': 'page',
            'message': '请输入想要检索的页面范围，一页20篇论文'
            # 这里需要添加validate关键字
        }
    ]
    answers = prompt(questions, style=style)
    return answers

def arguments_extract(answers):
    choose_key = {'主题':'topic', '题名':'title', '关键词':'keyword', '作者':'author', '院系':'department', '专业':'subject', '导师':'teacher', '年份':'year'}
    xuewei = {'硕士及博士':'0', '博士':'1', '硕士':'2'}
    px = {'按题名字顺序排序':'1', '按学位年度倒排序':'2'}
    info_url = "http://thesis.lib.sjtu.edu.cn/sub.asp?content={}&choose_key={}&xuewei={}&px={}&page=".format(quote(answers['content']), \
        choose_key[answers['choose_key']], \
        xuewei[answers['xuewei']], \
        px[answers['px']])
    print(info_url)
    pages = answers['page'].split('-')
    pages = [int(pages[0])]
    return info_url, pages

def confirmation(papers):
    if not PYINQUIRER_AVAILABLE:
        raise ImportError("PyInquirer is required for CLI mode. Install it with: pip install PyInquirer")
    
    print("\033[\033[1;32m 检索到了以下{}篇文章\033[0m".format(len(papers)))
    for i in papers:
        print('\033[1;31m 题目\033[0m', i['filename'], '\033[1;34m 作者\033[0m', i['author'], '\033[1;36m 导师\033[0m', i['mentor'], '\033[1;35m 年份\033[0m', i['year'])
        # 这里需要格式化输出对其一下
    questions = [
        {
            'type': 'confirm',
            'message': "确认下载{}篇文章吗？".format(len(papers)),
            'name': 'confirmation',
            'default': 'True'
        }
    ]
    answers = prompt(questions)
    return answers

def verify_name(paper_filename):
    if not os.path.exists('./papers'):
        os.mkdir('./papers')
    if paper_filename in os.listdir('./papers'):
        return True
    return False

def init(jpg_dir):
    """初始化文件夹路径
    """
    try:
        shutil.rmtree('./{}/'.format(jpg_dir))
        print("删除本地{}文件夹".format(jpg_dir))
    except Exception as e:
        print(e)
    try:
        os.mkdir('./{}/'.format(jpg_dir))
        print("新建本地{}文件夹".format(jpg_dir))
    except Exception as e:
        print(e)

def download_main_info(info_url: str, pages: list):
    papers = []
    total_count = 0
    total_pages = 0
    info_url = info_url
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
    }
    result = requests.Session()
    for page in range(pages[0], pages[0]+1):
        print("正在抓取第{}页的info".format(page))
        info_url_construction = info_url + str(page)
        response = result.get(info_url_construction, headers=headers, allow_redirects=False)
        html = etree.HTML(response.content, etree.HTMLParser())
        
        # 获取总记录数和总页数
        try:
            import re
            # 从页面文本中查找 "共 XXX 条记录" 模式
            page_text = ''.join(html.xpath('//text()'))
            
            # 查找 "，共" 和 "条记录" 之间的数字
            match = re.search(r'，共\s*(\d+)\s*条记录', page_text)
            if match:
                total_count = int(match.group(1))
                total_pages = (total_count + 19) // 20  # 每页20条，向上取整
                print(f"检索到总记录数: {total_count}, 总页数: {total_pages}")
            else:
                # 尝试其他模式
                match = re.search(r'共\s*(\d+)\s*条', page_text)
                if match:
                    total_count = int(match.group(1))
                    total_pages = (total_count + 19) // 20
                    print(f"检索到总记录数: {total_count}, 总页数: {total_pages}")
        except Exception as e:
            print(f"提取总记录数时出错: {e}")
        
        for i in range(2, 22):
            # 有些是论文保密，所以link需要错误处理
            info_dict = defaultdict(str)
            try:
                filename = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]//td[2]/text()'.format(i))[0]
                author = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[3]/div/text()'.format(i))[0]
                mentor = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[6]/div/text()'.format(i))[0]
                year = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[8]/div/text()'.format(i))[0]
                link = "http://thesis.lib.sjtu.edu.cn/" + html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[9]/div/a[2]/@href'.format(i))[0]
                info_dict['filename'] = filename
                info_dict['author'] = author
                info_dict['mentor'] = mentor
                info_dict['year'] = year
                info_dict['link'] = link
                papers.append(info_dict)
            except Exception as e:
                #print(e)
                pass
    
    # 如果没有从页面提取到总数，根据实际抓取的数据估算
    if total_count == 0 and len(papers) > 0:
        # 如果当前页有数据，至少说明有这一页
        total_count = len(papers)
        total_pages = pages[0]
        print(f"未能从页面提取总数，根据当前数据估算: 至少 {total_count} 条记录")
    
    print("总共抓取到{}个元数据信息".format(len(papers)))
    
    # 返回论文列表、总记录数和总页数
    return papers, total_count, total_pages

def download_jpg(url: str, jpg_dir: str):
    """下载论文链接为jpg
        :param url: 阅读全文链接
    """
    url = url
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
    }
    result = requests.Session()
    print("开始获取图片地址")
    response = result.get(url, headers=headers, allow_redirects=False)
    
    if 'Location' not in response.headers:
        print("错误：无法获取重定向地址，可能是论文未公开或链接失效")
        return
    
    url = response.headers['Location']
    response = result.get(url, headers=headers, allow_redirects=False)
    
    if 'Location' not in response.headers:
        print("错误：第二次重定向失败")
        return
    
    url = response.headers['Location']
    response = result.get(url, headers=headers, allow_redirects=False)
    
    if 'Location' not in response.headers:
        print("错误：第三次重定向失败")
        return
    
    url_bix = response.headers['Location'].split('?')[1]
    url = "http://thesis.lib.sjtu.edu.cn:8443/read/jumpServlet?page=1&" + url_bix
    response = result.get(url, headers=headers, allow_redirects=False)
    urls = json.loads(response.content.decode())
    print("已经获取到图片地址")
    i = 1
    while(True):
        fig_url = "http://thesis.lib.sjtu.edu.cn:8443/read/" + urls['list'][0]['src'].split('_')[0] + "_{0:05d}".format(i) + ".jpg"
        response = result.get(fig_url, headers=headers).content
        rtext = result.get(fig_url, headers=headers).text
        # print(fig_url)
        if ('HTTP状态 404 - 未找到' in result.get(fig_url, headers=headers).text):
            for t in range(10):
                time.sleep(2)
                rtext = result.get(fig_url, headers=headers).text
                if ('HTTP状态 404 - 未找到' in rtext): pass
                else: break
            if ('HTTP状态 404 - 未找到' in rtext):
                print(f"{fig_url}: HTTP状态 404 - 未找到")
                break
        while len(response) < 2000:
            response = result.get(fig_url, headers=headers).content
        # if len(response) == 746:
        #     #print(response)
        #     #print("资源无法访问了，网站挂了")
        #     break
        with open('./{}/{}.jpg'.format(jpg_dir, i), 'wb') as f:
            f.write(response)
            # print(len(response))
        print("正在采集第{}页".format(i))
        i = i + 1

def merge_pdf(paper_filename, jpg_dir):
    print("合并pdf文件")
    doc = pymupdf.open()
    imgs = []
    filename = f'./papers/{paper_filename}'
    img_path = './{}/'.format(jpg_dir)
    # if len(os.listdir('./{}/'.format(jpg_dir)))<100:
    #     print("文章{}下载错误，跳过".format(paper_filename))
    #     shutil.rmtree('./{}'.format(jpg_dir))
    #     return
    for img in os.listdir('./{}/'.format(jpg_dir)):
        imgs.append(img)
    imgs.sort(key=lambda x:int(x[:-4]))
    for img in imgs:
        img = pymupdf.open(img_path + img)
        rect = img[0].rect
        pdf_bytes = img.convert_to_pdf()
        img.close()
        pdf_img = pymupdf.open("pdf", pdf_bytes)
        doc.insert_pdf(pdf_img)
        pdf_img.close()
    doc.save(filename)
    doc.close()
    shutil.rmtree('./{}'.format(jpg_dir))

if __name__=='__main__':
    main()