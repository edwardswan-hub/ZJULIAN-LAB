
import pandas as pd
import json

def convert_excel_to_json(excel_path, json_path):
    """
    读取一个包含特定sheet的Excel文件，将其内容转换为一个结构化的JSON文件。

    Args:
        excel_path (str): 输入的Excel文件路径 (.xlsx).
        json_path (str): 输出的JSON文件路径 (.json).

    Returns:
        bool: 如果成功则返回 True, 否则返回 False.
    """
    try:
        xls = pd.ExcelFile(excel_path)
    except FileNotFoundError:
        print(f"错误: Excel文件未找到 at {excel_path}")
        return False
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}")
        return False

    all_data = {}
    sheet_map = {
        '看过的电影': 'watched',
        '在看的电影': 'watching',
        '想看的电影': 'wantToWatch'
    }

    for sheet_name, status_key in sheet_map.items():
        if sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                # 处理NaN值和数据类型，确保JSON序列化没问题
                df = df.fillna('')
                records = df.to_dict('records')
                
                # 清理和结构化数据
                cleaned_records = []
                for i, record in enumerate(records):
                    posters = str(record.get('海报链接', '')).split()
                    stills = str(record.get('剧照链接', '')).split()
                    
                    cleaned_records.append({
                        'id': f'{status_key}-{i}',
                        'title': record.get('标题', '未知标题'),
                        'year': str(record.get('年份', '')),
                        'director': record.get('导演', ''),
                        'actors': record.get('主要演员', ''),
                        'plot': record.get('剧情简介', '暂无简介'),
                        'posters': [p for p in posters if p.startswith('http')],
                        'stills': [s for s in stills if s.startswith('http')]
                    })
                all_data[status_key] = cleaned_records
            except Exception as e:
                print(f"处理Sheet '{sheet_name}' 时出错: {e}")
                # 即使某个sheet出错，也继续处理其他的
                all_data[status_key] = []
        else:
            # 如果sheet不存在，也为其创建一个空列表
            all_data[status_key] = []

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"成功将数据转换并保存到 {json_path}")
        return True
    except Exception as e:
        print(f"写入JSON文件时出错: {e}")
        return False

if __name__ == '__main__':
    # 这是一个可以直接运行进行测试的例子
    # 假设 '我的影视数据库索引.xlsx' 在 'scripts' 文件夹下
    # 我们在 'backend' 文件夹下运行，所以路径需要正确指向
    source_excel = '../scripts/我的影视数据库索引.xlsx'
    output_json = './movies.json'
    
    if convert_excel_to_json(source_excel, output_json):
        print("测试转换成功！")
    else:
        print("测试转换失败。")

