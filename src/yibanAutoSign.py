"""
new Env(易班自动签到)
cron: 59 20 * * *
"""

import os
import sys
import threading
import time
import datetime

# 添加项目根目录到路径，使用本地fyiban库
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from serverChan import ServerChan
from userData import user_data
from fyiban import Yiban

count = 5  # 增加重试次数到5次

# 网络请求超时设置
import requests
requests.packages.urllib3.util.connection.HAS_IPV6 = False
requests.adapters.DEFAULT_RETRIES = 3

def is_sign_time():
    """检查是否为签到时间"""
    now = datetime.datetime.now()
    weekday = now.weekday()  # 0-6，0是周一，6是周日
    
    # 检查是否为周六或周日
    if weekday in [5, 6]:  # 5是周六，6是周日
        print(f"📅 今天是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][weekday]}，无需签到")
        return False
    
    # 检查是否在6:30-7:50之间
    hour = now.hour
    minute = now.minute
    total_minutes = hour * 60 + minute
    
    start_time = 6 * 60 + 30  # 6:30
    end_time = 7 * 60 + 50    # 7:50
    
    if start_time <= total_minutes <= end_time:
        print(f"✅ 当前时间{hour:02d}:{minute:02d}，在签到时间范围内")
        return True
    else:
        print(f"⏰ 当前时间{hour:02d}:{minute:02d}，不在签到时间范围内")
        print(f"   签到时间：周一至周五 6:30-7:50")
        return False

def wait_for_sign_time():
    """等待到签到时间"""
    while True:
        now = datetime.datetime.now()
        weekday = now.weekday()
        
        # 检查是否为周六或周日
        if weekday in [5, 6]:
            print(f"📅 今天是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][weekday]}，无需签到")
            return False
        
        # 检查是否在签到时间范围内
        hour = now.hour
        minute = now.minute
        total_minutes = hour * 60 + minute
        
        start_time = 6 * 60 + 30  # 6:30
        end_time = 7 * 60 + 50    # 7:50
        
        if start_time <= total_minutes <= end_time:
            print(f"✅ 到达签到时间：{hour:02d}:{minute:02d}")
            return True
        
        # 计算等待时间
        if total_minutes < start_time:
            # 等待到签到开始
            wait_seconds = (start_time - total_minutes) * 60
            print(f"⏳ 等待签到开始，还需{wait_seconds // 60}分钟")
            time.sleep(min(wait_seconds, 3600))  # 最多等待1小时
        else:
            # 今天签到时间已过
            print(f"❌ 今天签到时间已过，明天6:30开始")
            return False


def start_sign(user: dict):
    server_chan = ServerChan("易班签到详情", user["SendKey"])
    for i in range(count):
        # 检查是否为签到时间
        if not is_sign_time():
            # 等待到签到时间
            if not wait_for_sign_time():
                # 无需签到或时间已过
                server_chan.log(f'{user["Phone"]}: 今天无需签到或签到时间已过').send_msg()
                return
        
        print(f"📡 尝试连接易班服务器 ({i + 1}/{count})...")
        yb = Yiban(user["Phone"], user["PassWord"])
        try:
            # 直接提交签到，不再从API获取时间范围
            back = yb.submit_sign_feedback(user["Address"])
            print(f"✅ 签到成功: {back}")
            server_chan.log(f'{user["Phone"]}: {back}').send_msg()
            return
        except Exception as e:
            # 一般是登录失败或登录超时
            error_msg = str(e)
            print(f"❌ 出现错误: {error_msg}")
            print(f"⏳ 等待后重试 ({i + 1}/{count})")
            # 根据尝试次数增加等待时间
            wait_time = min(5 + i * 2, 15)  # 5, 7, 9, 11, 13秒
            print(f"   等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            # 重新进行登录操作
            continue
    server_chan.log(f'{user["Phone"]} 重试机会使用完，签到失败').send_msg()
    print("❌ 所有重试机会已用完，签到失败")


DEBUG = True if sys.gettrace() else False

if __name__ == "__main__":
    env = os.getenv("skip")
    if env is not None:
        env = env.split(",")
    else:
        env = ""

    for user in user_data:
        if user["Phone"] in env or not user.get("enable", True):
            print(f'用户 {user["Phone"]} 在跳过列表')
            continue

        if DEBUG:
            start_sign(user)
        else:
            threading.Thread(target=start_sign, args=(user,)).start()
