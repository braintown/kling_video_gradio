---
title: 可灵ai视频_gradio
app_file: gradio_image_*.py
sdk: gradio
sdk_version: 5.0.1
---
# 可灵ai 视频生成

* 快手可灵ai视频生成gradio界面，功能与可灵ai页面基本一致。
* 支持并发数为3
* gradio页面中文生视频和图生视频可同时进行


## use gradio create kling video UI for txt2video and img2video

* gradio_image_base64.py is the base64 image to video
* gradio_image_url.py is the url image to video,need to setting the oss url
* [kling_video_gradio](https://github.com/braintown/kling_video_gradio.git)

## Usage
### Prerequisite: [Kling](https://kling.ai/) API Key
1. Set the `ak` and `sk` in environment before gradio starts or set it on the node.

