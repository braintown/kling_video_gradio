import gradio as gr


# 定义一个简单的视频生成函数
def generate_video(text, weight):
    # 这里可以插入生成视频的逻辑
    return "path_to_generated_video.mp4"


# 历史视频列表
history_videos = ["history_video1.mp4", "history_video2.mp4"]

# 创建Gradio界面
with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column():
            text_input = gr.Textbox(label="输入文本")
            weight_slider = gr.Slider(minimum=0, maximum=100, label="调节权重")
            generate_button = gr.Button("生成视频")

        with gr.Column():
            video_output = gr.Video(label="生成的视频")

        with gr.Column():
            history_list = gr.Dropdown(choices=history_videos, label="历史视频")
            play_button = gr.Button("播放历史视频")

    # 绑定生成视频按钮的点击事件
    generate_button.click(
        fn=generate_video,
        inputs=[text_input, weight_slider],
        outputs=video_output
    )


    # 绑定播放历史视频按钮的点击事件
    def play_history_video(video):
        return video


    play_button.click(
        fn=play_history_video,
        inputs=history_list,
        outputs=video_output
    )

# 启动Gradio应用
demo.launch()