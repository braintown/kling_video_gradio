import gradio as gr
import json
import requests
import time
import jwt
import base64
from io import BytesIO
import os


ak = os.environ.get("ak", None)  # 填写access key
sk = os.environ.get("sk", None)  # 填写secret key


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


url_txt = "https://api.klingai.com/v1/videos/text2video"
url_img = "https://api.klingai.com/v1/videos/image2video"


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

    if control_type != "none":
        camera_control = {"type": control_type}
        if control_type == "simple":
            camera_control["config"] = config
        payload["camera_control"] = camera_control

    payload_str = json.dumps(payload)
    print("payload_str", payload_str)
    response = requests.request("POST", url_txt, headers=headers, data=payload_str)

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


# 将PIL图像转换为Base64字符串
def pil_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    return img_base64


# 处理图片生成视频的回调函数
def process_image_to_video(token, model, image, tail_image, prompt, negative, mode, duration, weight,
                           history_videos_img):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # 转换上传的图片和尾帧图片为Base64
    img_base64 = pil_to_base64(image) if image is not None else ""
    tail_img_base64 = pil_to_base64(tail_image) if tail_image is not None else ""

    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative,
        "mode": mode,
        "duration": duration,
        "cfg_scale": weight,
        "image": img_base64,
        "tail_image": tail_img_base64
    }

    payload_str = json.dumps(payload)
    print("payload_str", payload_str)

    # 发送请求到API
    response = requests.request("POST", url_img, headers=headers, data=payload_str)

    # 检查响应
    if response.status_code != 200:
        print(f"错误：{response.status_code}")
        return None, None

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


with gr.Blocks() as demo:
    gr.Markdown("# 视频生成工具")

    with gr.Tabs() as tabs:
        with gr.TabItem("文字生成视频"):
            with gr.Row():
                with gr.Column():
                    model = gr.Dropdown(choices=["kling-v1"], label="模型选择", value="kling-v1")
                    text_input = gr.Textbox(label="正向提示词(必填)", value="1 cadillac car driving behind the sea")
                    negative = gr.Textbox(label="反向提示词(选填)", value="")
                    mode = gr.Dropdown(choices=["std", "pro"], label="std:更快，pro:质量更好", value="std")
                    aspect_ratio = gr.Dropdown(choices=["16:9", "9:16", "1:1"], label="视频比例", value="16:9")
                    duration = gr.Dropdown(choices=[5, 10], label="视频时长", value=5)
                    weight_slider = gr.Slider(minimum=0, maximum=1, step=0.1,
                                              label="调节权重，值越大，模型自由度越小，相关性越强", value=0.5)
                    control_type = gr.Dropdown(
                        label="摄像机控制类型，仅5s&标准std的情况下支持镜头控制，其他情况不支持",
                        choices=["none", "simple", "down_back", "forward_up", "right_turn_forward",
                                 "left_turn_forward"],
                        value="none"
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
                with gr.Column():
                    history_videos_state = gr.State([])
                    history_list = gr.Dropdown(choices=[], label="历史视频")
                    play_button = gr.Button("播放历史视频")


                def update_config_visibility(new_control_type):
                    return gr.update(visible=(new_control_type == "simple"))


                control_type.change(
                    fn=update_config_visibility,
                    inputs=control_type,
                    outputs=config_row
                )


                def process_generate_video(model, prompt, negative, mode, aspect_ratio, duration, weight,
                                           control_type,
                                           horizontal,
                                           vertical, pan, tilt, roll, zoom, history_videos):
                    token = encode_jwt_token(ak, sk)  # 在每次生成视频时生成新token
                    config = {
                        "horizontal": horizontal, "vertical": vertical, "pan": pan, "tilt": tilt, "roll": roll,
                        "zoom": zoom
                    }
                    filtered_config = {k: v for k, v in config.items() if v != 0}

                    video_id, video_url = generate_video(token, model, prompt, negative, mode, aspect_ratio,
                                                         duration, weight,
                                                         control_type, filtered_config)
                    history_videos.append((video_id, video_url))

                    display_choices = [f"{i + 1}. {video_id}" for i, (video_id, _) in enumerate(history_videos)]
                    return video_url, gr.Dropdown(choices=display_choices)


                generate_button.click(
                    fn=process_generate_video,
                    inputs=[
                        model, text_input, negative, mode, aspect_ratio, duration, weight_slider,
                        control_type, horizontal, vertical, pan, tilt, roll, zoom, history_videos_state
                    ],
                    outputs=[video_output, history_list]
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
                    text_input = gr.Textbox(label="正向提示词(必填)",
                                            value="1 cadillac car driving behind the sea")
                    negative = gr.Textbox(label="反向提示词(选填)", value="")
                    mode = gr.Dropdown(choices=["std", "pro"], label="std:更快，pro:质量更好", value="std")
                    duration = gr.Dropdown(choices=[5, 10], label="视频时长", value=5)
                    weight_slider = gr.Slider(minimum=0, maximum=1, step=0.1,
                                              label="调节权重，值越大，模型自由度越小，相关性越强", value=0.5)
                    generate_button_img = gr.Button("生成视频")
                with gr.Column():
                    video_output_img = gr.Video(label="生成的视频")
                with gr.Column():
                    history_videos_state_img = gr.State([])
                    history_list_img = gr.Dropdown(choices=[], label="历史视频")
                    play_button_img = gr.Button("播放历史视频")
            generate_button_img.click(
                fn=lambda model, image, tail_image, prompt, negative, mode, duration, weight,history_videos_img:
                process_image_to_video(
                    encode_jwt_token(ak, sk), model, image, tail_image, prompt, negative, mode, duration,
                    weight,
                    history_videos_img
                ),
                inputs=[model, image_input, image_tail, text_input, negative, mode, duration, weight_slider,
                        history_videos_state_img],
                outputs=[video_output_img, history_list_img, history_videos_state_img]
            )


    def play_history_video(selected, history_videos):
        idx = int(selected.split(".")[0]) - 1
        video_url = history_videos[idx][1]
        return video_url


    def play_history_image_video(selected, history_videos):
        idx = int(selected.split(".")[0]) - 1
        video_url = history_videos[idx][1]
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
