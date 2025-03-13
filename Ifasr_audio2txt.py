# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import time
import requests
import urllib

lfasr_host = 'https://raasr.xfyun.cn/v2/api'
# 请求的接口名
api_upload = '/upload'
api_get_result = '/getResult'


class RequestApi(object):
    def __init__(self, appid, secret_key, upload_file_path):
        self.appid = appid
        self.secret_key = secret_key
        self.upload_file_path = upload_file_path
        self.ts = str(int(time.time()))
        self.signa = self.get_signa()

    def get_signa(self):
        appid = self.appid
        secret_key = self.secret_key
        m2 = hashlib.md5()
        m2.update((appid + self.ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        # 以secret_key为key, 上面的md5为msg， 使用hashlib.sha1加密结果为signa
        signa = hmac.new(secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        return signa

    def upload(self):
        print("上传部分：")
        upload_file_path = self.upload_file_path
        file_len = os.path.getsize(upload_file_path)
        file_name = os.path.basename(upload_file_path)

        param_dict = {}
        param_dict['appId'] = self.appid
        param_dict['signa'] = self.signa
        param_dict['ts'] = self.ts
        param_dict["fileSize"] = file_len
        param_dict["fileName"] = file_name
        param_dict["duration"] = "200"
        param_dict["candidate"] = "1"  # 添加候选词参数
        # 添加说话人分离相关参数
        param_dict["roleType"] = "1" # 启用角色分离
        param_dict["roleNum"] = "0"  # 指定说话人数量，根据您的实际情况调整 0为自动 但是如果可以确定角色，可以指定角色数，可以提高准确率
        print("upload参数：", param_dict)
        data = open(upload_file_path, 'rb').read(file_len)

        response = requests.post(url=lfasr_host + api_upload + "?" + urllib.parse.urlencode(param_dict),
                                 headers={"Content-type": "application/json"}, data=data)
        print("upload_url:", response.request.url)
        result = json.loads(response.text)
        print("upload resp:", result)
        return result

    def get_result(self):
        uploadresp = self.upload()
        orderId = uploadresp['content']['orderId']
        param_dict = {}
        param_dict['appId'] = self.appid
        param_dict['signa'] = self.signa
        param_dict['ts'] = self.ts
        param_dict['orderId'] = orderId
        param_dict['resultType'] = "transfer"
        print("")
        print("查询部分：")
        print("get result参数：", param_dict)
        status = 3
        # 建议使用回调的方式查询结果，查询接口有请求频率限制
        while status == 3:
            response = requests.post(url=lfasr_host + api_get_result + "?" + urllib.parse.urlencode(param_dict),
                                     headers={"Content-type": "application/json"})
            result = json.loads(response.text)
            print(result)
            status = result['content']['orderInfo']['status']
            print("status=", status)
            if status == 4:
                break
            time.sleep(5)
        print("get_result resp:", result)
        return result


# 保存结果为txt文件
# 保存结果为txt文件，按时间顺序排列，每句话前标注发言人序号
def save_to_txt(result, output_file):
    try:
        # 提取识别结果
        order_result = result['content']['orderResult']
        # 将orderResult从字符串解析为JSON
        order_result = json.loads(order_result)
        
        # 提取lattice2中的文本
        with open(output_file, 'w', encoding='utf-8') as f:
            # 保存所有内容，不分段落
            all_contents = []
            speaker_map = {}  # 用于存储说话人映射
            
            # 首先提取所有内容并记录说话人
            for item in order_result.get('lattice2', []):
                spk = item.get('spk', '未知')
                if spk not in speaker_map:
                    speaker_map[spk] = len(speaker_map) + 1
                
                begin_time = int(item.get('begin', 0))
                end_time = int(item.get('end', 0))
                
                json_1best = item.get('json_1best', {})
                if not json_1best:
                    continue
                
                st = json_1best.get('st', {})
                if not st:
                    continue
                
                # 提取文本内容
                text = ""
                for r in st.get('rt', []):
                    for w in r.get('ws', []):
                        for c in w.get('cw', []):
                            word = c.get('w', '')
                            text += word
                
                # 如果文本不为空，则添加到内容列表
                if text.strip():
                    all_contents.append({
                        'speaker_id': speaker_map[spk],
                        'speaker': spk,
                        'begin_time': begin_time,
                        'end_time': end_time,
                        'text': text
                    })
            
            # 按开始时间排序所有内容
            all_contents.sort(key=lambda x: x['begin_time'])
            
            # 写入文件头
            f.write("# 语音识别结果\n\n")
            f.write("## 发言人列表\n")
            for spk, speaker_id in sorted(speaker_map.items(), key=lambda x: x[1]):
                f.write(f"- 发言人 {speaker_id}: {spk}\n")
            f.write("\n## 按时间顺序的对话内容\n\n")
            
            # 然后按时间顺序写入所有内容
            for i, content in enumerate(all_contents, 1):
                begin_time = content['begin_time']
                speaker_id = content['speaker_id']
                # 格式化时间戳 [分钟:秒.毫秒]
                timestamp = f"[{begin_time // 60000:02d}:{(begin_time % 60000) // 1000:02d}.{(begin_time % 1000):03d}]"
                f.write(f"{timestamp} [发言人{speaker_id}] {content['text']}\n")
            
        print(f"结果已保存到文件: {output_file}")
    except Exception as e:
        print("保存结果时出错:", e)
        import traceback
        print(traceback.format_exc())


# 输入讯飞开放平台的appid，secret_key和待转写的文件路径
if __name__ == '__main__':
    api = RequestApi(appid="xxx",
                     secret_key="xxx",
                     upload_file_path=r"audio/lfasr.wav")

    result = api.get_result()
    # 定义输出文件路径
    output_file = "result.txt"
    # 保存结果到txt文件
    save_to_txt(result, output_file)
