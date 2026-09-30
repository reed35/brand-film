# brand-film

给一个公司名，用纯代码（numpy / Pillow / ffmpeg，不用任何视频、图片、音乐模型）生成一支 ≤90 秒、1080p、带原创配乐的品牌宣传片。

完整流程见 `SKILL.md`，字段说明见 `references/film_schema.md`，风格规则见 `references/style_guide.md`。

## 安装

```bash
pip install numpy pillow imageio-ffmpeg
# Linux 需要中文字体，例如：sudo apt-get install -y fonts-noto-cjk
python scripts/make_film.py doctor
```
