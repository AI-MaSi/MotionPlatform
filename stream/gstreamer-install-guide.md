# GStreamer Installation Guide

## On Excavator (Linux)

1. Update system packages:
```bash
sudo apt-get update
```

2. Install GStreamer and dependencies:
```bash
sudo apt-get install libgstreamer1.0-dev \
     libgstreamer-plugins-base1.0-dev \
     libgstreamer-plugins-bad1.0-dev \
     gstreamer1.0-plugins-ugly \
     gstreamer1.0-tools \
     gstreamer1.0-gl \
     gstreamer1.0-gtk3
sudo apt-get install gstreamer1.0-qt5
```

## On Receiving PC (Windows 10)

1. Download GStreamer:
   - URL: https://gstreamer.freedesktop.org/data/pkg/windows/1.24.10/msvc/gstreamer-1.0-msvc-x86_64-1.24.10.msi
   - Install the downloaded package. Select "Complete" installation!

2. Add to PATH:
   - Press Windows key + R
   - Type `sysdm.cpl` and press Enter
   - Go to "Advanced" tab
   - Click "Environment Variables"
   - Under "System Variables", select "Path"
   - Click "Edit" → "New"
   - Add: `C:\gstreamer\1.0\msvc_x86_64\bin`
   - Click "OK" on all windows
   - Restart Command Prompt/PowerShell

## Usage (Low latency H264 over RTP/UDP)
(assuming camera is `/dev/video0` and receiver hostname/IP is set)

On excavator (sender):
```bash
gst-launch-1.0 -v v4l2src device=/dev/video0 do-timestamp=true \
  ! image/jpeg,width=1280,height=720,framerate=30/1 \
  ! jpegdec \
  ! queue leaky=downstream max-size-buffers=1 max-size-bytes=0 max-size-time=0 \
  ! videoconvert \
  ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=15 bframes=0 sliced-threads=true byte-stream=true threads=1 \
  ! h264parse config-interval=-1 \
  ! rtph264pay pt=96 config-interval=1 mtu=1200 \
  ! udpsink host=<receiver_hostname_or_IP> port=5005 sync=false async=false
```

On receiving PC (Windows):
```bash
gst-launch-1.0 -v udpsrc port=5005 caps="application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000" \
  ! queue \
  ! rtpjitterbuffer latency=0 drop-on-latency=true \
  ! rtph264depay \
  ! avdec_h264 \
  ! videoflip method=rotate-180 \
  ! videoconvert \
  ! autovideosink sync=false
```

> **Note:** `videoflip method=rotate-180` corrects an upside-down camera mount — remove it if your camera is already oriented correctly.
> **Tuning:** `bitrate` (sender) and `mtu` on `rtph264pay` are worth experimenting with — lower bitrate reduces bandwidth at the cost of quality, and MTU may need adjusting depending on your network (default 1200 is safe for most setups; try 1400 on local networks).
