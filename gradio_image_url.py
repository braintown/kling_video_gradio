import os

import gradio as gr
import json
import requests
import time
import jwt
import pymysql
from PIL import Image
from io import BytesIO
import aiohttp
import asyncio
from datetime import datetime

ACCESS_KEY = os.environ.get('ACCESS_KEY', None)  # 填写access key
SECRET_KEY = os.environ.get('SECRET_KEY', None)  # 填写secret key
URL_TEXT2VIDEO = "https://api.klingai.com/v1/videos/text2video"
URL_IMAGE2VIDEO = "https://api.klingai.com/v1/videos/image2video"


def encode_jwt_token(ak, sk):
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,  # 有效时间，此处示例代表当前时间+1800s(30min)
        "nbf": int(time.time()) - 5  # 开始生效的时间，此处示例代表当前时间-5秒
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token

def generate_video(token, model, prompt, negative, mode, aspect_ratio, duration, weight, control_type, config):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative,
        "mode": mode,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "cfg_scale": weight,
    }

    # if payload["prompt"] == "" or None:
    #     raise ValueError("Prompt cannot be empty")

    if control_type != "none":
        camera_control = {"type": control_type}
        if control_type == "simple":
            camera_control["config"] = config
        payload["camera_control"] = camera_control



    payload_str = json.dumps(payload)
    print("payload_str", payload_str)
    response = requests.request("POST", URL_TEXT2VIDEO, headers=headers, data=payload_str)

    ids = json.loads(response.text)["data"]["task_id"]
    print("Task ID:", ids)

    url_video = f"https://api.klingai.com/v1/videos/text2video/{ids}"
    result = json.loads(requests.get(url_video, headers=headers).text)["data"]["task_status"]
    print("Initial Task Status:", result)

    while result != "succeed":
        time.sleep(5)
        response_video = requests.get(url_video, headers=headers)
        result = json.loads(response_video.text)["data"]["task_status"]
        print("Updated Task Status:", result)

    video_data = json.loads(response_video.text)["data"]["task_result"]["videos"][0]
    video_url = video_data["url"]
    video_id = video_data["id"]

    print("Generated Video ID:", video_id)


    return video_id, video_url

async def upload_image_to_blob(image: Image, requested_url: str):
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_byte_arr = img_byte_arr.getvalue()
    url = "https://ai-dev.gempoll.com/v2/api/workbench/uploadBlob"
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("file", img_byte_arr, filename="image.png", content_type='image/png')
        async with session.post(url, data=data) as response:
            if response.status == 200:
                response_json = await response.json()
                code = response_json["code"]
                if code != 200:
                    print(f"Error uploading image: {response_json}\nRequestedURL = {requested_url}")
                    return None
                return response_json.get("data")
            else:
                print(
                    f"Error uploading image: {response.status}\n{await response.text()}\nRequestedURL = {requested_url}")
                return None

# 处理图片生成视频的回调函数
def process_image_to_video(token, model, image, tail_image, prompt, negative, mode, duration, weight,
                           history_videos_img):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    if not prompt:
        return gr.update(value="<span style='color:red; font-size: 20px;'>提示词必填</span>",
                         visible=True), None, None, None
    # 异步上传图片并获取 URL
    async def upload_images():
        img_url = await upload_image_to_blob(image, URL_IMAGE2VIDEO) if image is not None else ""
        tail_img_url = await upload_image_to_blob(tail_image, URL_IMAGE2VIDEO) if tail_image is not None else ""
        return img_url, tail_img_url

    # 获取上传的图片 URL
    img_url, tail_img_url = asyncio.run(upload_images())

    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative,
        "mode": mode,
        "duration": duration,
        "cfg_scale": weight,
        "image": img_url,  # 修改为 URL
        "image_tail": tail_img_url  # 修改为 URL
    }
    payload_str = json.dumps(payload)
    print("payload_str", payload_str)

    # 发送请求到API
    response = requests.request("POST", URL_IMAGE2VIDEO, headers=headers, data=payload_str)

    # 检查响应
    if response.status_code != 200:
        print(f"错误：{response.status_code}")
        return None, None, history_videos_img

    # 结果处理
    ids = json.loads(response.text)["data"]["task_id"]
    print("Task ID:", ids)

    url_video = f"https://api.klingai.com/v1/videos/image2video/{ids}"
    result = json.loads(requests.get(url_video, headers=headers).text)["data"]["task_status"]
    print("Initial Task Status:", result)

    while result != "succeed":
        time.sleep(5)
        response_video = requests.get(url_video, headers=headers)
        result = json.loads(response_video.text)["data"]["task_status"]
        print("Updated Task Status:", result)

    video_data = json.loads(response_video.text)["data"]["task_result"]["videos"][0]
    video_url = video_data["url"]
    video_id = video_data["id"]

    print("Generated Video ID:", video_id)
    # 更新历史记录
    history_videos_img.append((video_id, video_url))
    display_choices = [f"{i + 1}. {video_id}" for i, (video_id, _) in enumerate(history_videos_img)]

    return video_url, gr.update(choices=display_choices), history_videos_img


# 映射字典
control_type_mapping = {
    "无": "none",
    "自定义": "simple",
    "下退": "down_back",
    "前进": "forward_up",
    "右转前进": "right_turn_forward",
    "左转前进": "left_turn_forward"
}


# 函数将中文转换为英文
def translate_control_type(chosen_type):
    return control_type_mapping[chosen_type]


with gr.Blocks() as demo:
    gr.Markdown("# 视频生成工具")

    with gr.Tabs() as tabs:
        with gr.TabItem("文字生成视频"):
            with gr.Row():
                with gr.Column():
                    model = gr.Dropdown(choices=["kling-v1"], label="模型选择", value="kling-v1")
                    text_input = gr.Textbox(label="正向提示词(必填)(支持中文)", value="1 cadillac car driving on the street")
                    negative = gr.Textbox(label="反向提示词(选填)：不想出现的元素、风格", value="")
                    mode = gr.Dropdown(choices=["std", "pro"], label="std:更快，pro:质量更好", value="std")
                    aspect_ratio = gr.Dropdown(choices=["16:9", "9:16", "1:1"], label="视频比例", value="16:9")
                    duration = gr.Dropdown(choices=[5, 10], label="视频时长", value=5)
                    weight_slider = gr.Slider(minimum=0, maximum=1, step=0.1,
                                              label="调节权重，值越大，模型自由度越小，相关性越强", value=0.5)

                    control_type = gr.Dropdown(
                        label="摄像机控制类型，仅5s&标准std的情况下支持镜头控制，其他情况不支持",
                        choices=list(control_type_mapping.keys()),  # 使用中文选项
                        value="无"
                    )

                    config_row = gr.Row(visible=False)  # 用于包含摄像机控制配置信息
                    with config_row:
                        horizontal = gr.Slider(minimum=-10, maximum=10, step=0.1, label="水平运镜 [horizontal]",
                                               value=0)
                        vertical = gr.Slider(minimum=-10, maximum=10, step=0.1, label="垂直运镜 [vertical]", value=0)
                        pan = gr.Slider(minimum=-10, maximum=10, step=0.1, label="水平摇镜 [pan]", value=0)
                        tilt = gr.Slider(minimum=-10, maximum=10, step=0.1, label="垂直摇镜 [tilt]", value=0)
                        roll = gr.Slider(minimum=-10, maximum=10, step=0.1, label="旋转运镜 [roll]", value=0)
                        zoom = gr.Slider(minimum=-10, maximum=10, step=0.1, label="变焦 [zoom]", value=0)

                    generate_button = gr.Button("生成视频")
                with gr.Column():
                    video_output = gr.Video(label="生成的视频")
                    error_output = gr.Markdown("", visible=False)  # 用于显示错误信息

                with gr.Column():
                    history_videos_state = gr.State([])
                    history_list = gr.Dropdown(choices=[], label="历史视频")
                    play_button = gr.Button("播放历史视频")


                def update_config_visibility(new_control_type):
                    return gr.update(visible=(new_control_type == "自定义"))


                control_type.change(
                    fn=update_config_visibility,
                    inputs=control_type,
                    outputs=config_row
                )


                def process_generate_video(model, prompt, negative, mode, aspect_ratio, duration, weight,
                                           control_type,
                                           horizontal, vertical, pan, tilt, roll, zoom, history_videos):
                    # 如果提示词为空，则显示错误信息
                    if not prompt:
                        return gr.update(value="<span style='color:red; font-size: 20px;'>提示词必填</span>",
                                         visible=True), None, history_videos

                    # 如果持续时间不为5s或模式不为标准，并且摄像机控制类型不为"无"，则报错
                    if duration != 5 or mode != "std" and control_type != "无":
                        return gr.update(
                            value="<span style='color:red; font-size: 20px;'>必须在5s&标准std的情况下支持镜头控制</span>",
                            visible=True), None, history_videos

                    token = encode_jwt_token(ACCESS_KEY, SECRET_KEY)  # 在每次生成视频时生成新token
                    config = {
                        "horizontal": horizontal, "vertical": vertical, "pan": pan, "tilt": tilt, "roll": roll,
                        "zoom": zoom
                    }
                    filtered_config = {k: v for k, v in config.items() if v != 0}

                    # 将中文转换为英文
                    control_type_en = translate_control_type(control_type)

                    video_id, video_url = generate_video(token, model, prompt, negative, mode, aspect_ratio,
                                                         duration, weight, control_type_en, filtered_config)
                    history_videos.append((video_id, video_url))

                    display_choices = [f"{i + 1}. {video_id}" for i, (video_id, _) in enumerate(history_videos)]

                    # 返回空字符串表示没有错误
                    return gr.update(value="", visible=False), video_url, gr.update(choices=display_choices)


                generate_button.click(
                    fn=process_generate_video,
                    inputs=[
                        model, text_input, negative, mode, aspect_ratio, duration, weight_slider,
                        control_type, horizontal, vertical, pan, tilt, roll, zoom, history_videos_state
                    ],
                    outputs=[error_output, video_output, history_list]
                )


                def play_history_video(selected, history_videos):
                    idx = int(selected.split(".")[0]) - 1
                    video_url = history_videos[idx][1]
                    return video_url


                play_button.click(
                    fn=play_history_video,
                    inputs=[history_list, history_videos_state],
                    outputs=video_output
                )

        with gr.TabItem("图片生成视频"):
            with gr.Row():
                with gr.Column():
                    model = gr.Dropdown(choices=["kling-v1"], label="模型选择", value="kling-v1")
                    image_input = gr.Image(type="pil",
                                           label="上传图片，支持.jpg / .jpeg / .png，文件大小不能超过10MB，图片分辨率不小于300*300px")
                    image_tail = gr.Image(type="pil", label="尾帧图片")
                    text_input = gr.Textbox(label="正向提示词(必填)(支持中文)", value="1 cadillac car driving on the street")
                    negative = gr.Textbox(label="反向提示词(选填)：不想出现的元素、风格", value="")
                    mode = gr.Dropdown(choices=["std", "pro"], label="std:更快，pro:质量更好", value="std")
                    duration = gr.Dropdown(choices=[5, 10], label="视频时长", value=5)
                    weight_slider = gr.Slider(minimum=0, maximum=1, step=0.1,
                                              label="调节权重，值越大，模型自由度越小，相关性越强", value=0.5)
                    generate_button_img = gr.Button("生成视频")
                with gr.Column():
                    video_output_img = gr.Video(label="生成的视频")
                    error_output_img = gr.Markdown("", visible=False)  # 用于显示错误信息
                with gr.Column():
                    history_videos_state_img = gr.State([])
                    history_list_img = gr.Dropdown(choices=[], label="历史视频")
                    play_button_img = gr.Button("播放历史视频")

            generate_button_img.click(
                fn=lambda model, image, tail_image, prompt, negative, mode, duration, weight, history_videos_img:
                process_image_to_video(
                    encode_jwt_token(ACCESS_KEY, SECRET_KEY), model, image, tail_image, prompt, negative, mode,
                    duration,
                    weight, history_videos_img
                ),
                inputs=[model, image_input, image_tail, text_input, negative, mode, duration, weight_slider,
                        history_videos_state_img],
                outputs=[error_output_img, video_output_img, history_list_img, history_videos_state_img]
            )


    def play_history_video(selected, history_videos):
        idx = int(selected.split(".")[0]) - 1
        video_url = history_videos[idx][1]
        return video_url


    def play_history_image_video(selected, history_videos_img):
        idx = int(selected.split(".")[0]) - 1
        video_url = history_videos_img[idx][1]
        return video_url


    play_button.click(
        fn=play_history_video,
        inputs=[history_list, history_videos_state],
        outputs=video_output
    )
    play_button_img.click(
        fn=play_history_image_video,
        inputs=[history_list_img, history_videos_state_img],
        outputs=video_output_img
    )

demo.launch(server_name="0.0.0.0", server_port=1111, share=False)

