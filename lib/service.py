# -*- coding: utf-8 -*-


from urllib.parse import unquote

from yt_dlp import YoutubeDL

from iapc import public, Client, Service
from nuttig import getSetting, localizedString, notify, ICONERROR


# ------------------------------------------------------------------------------
# YtDlpVideo

class YtDlpVideo(dict):

    def __init__(self, info, captions=False):
        subtitles = info.get("subtitles", {})
        if not subtitles and captions:
            subtitles = info.get("automatic_captions", {})
        super(YtDlpVideo, self).__init__(
            video_id=info.get("id"),
            title=info.get("fulltitle", ""),
            description=info.get("description", ""),
            channel_id=info.get("channel_id"),
            channel=info.get("channel", ""),
            duration=info.get("duration", -1),
            is_live=info.get("is_live", False),
            url=info.get("manifest_url"),
            thumbnail=info.get("thumbnail"),
            like_count=info.get("like_count", 0),
            view_count=info.get("view_count", 0),
            timestamp=info.get("timestamp", 0),
            formats=info.get("formats", []),
            subtitles=subtitles
        )


# ------------------------------------------------------------------------------
# YtDlpService

class YtDlpService(Service):

    __fps_limits__ = {0: 32101, 30: 32102}

    __codecs__ = {
        "avc1": {"label": 33101, "names": ("avc1", )},
        "mp4a": {"label": 33102, "names": ("mp4a", )},
        "vp09": {"label": 33103, "names": ("vp09", "vp9")},
        "opus": {"label": 33104, "names": ("opus", )},
        "av01": {"label": 33105, "names": ("av01", )}
    }

    def __init__(self, *args, **kwargs):
        super(YtDlpService, self).__init__(*args, **kwargs)
        self.__extractor__ = YoutubeDL()
        self.__manifests__ = Client("service.manifests.mpd")
        self.__streamTypes__ = {
            "video": self.__video_stream__,
            "audio": self.__audio_stream__
        }
        self.__supportedSubtitles__ = ("vtt",)

    def __setup__(self):

        # include automatic captions
        self.__captions__ = getSetting("subs.captions", bool)
        self.logger.info(f"{localizedString(31100)}: {self.__captions__}")

        # limit fps
        self.__fps__ = getSetting("fps.limit", int)
        self.logger.info(
            f"{localizedString(32100)}: "
            f"{localizedString(self.__fps_limits__[self.__fps__])}"
        )

        # exclude codecs
        self.__exclude__ = []
        labels = None
        if (exclude := getSetting("codecs.exclude")):
            exclude = exclude.split(",")
            self.__exclude__ = [
                name for codec in exclude
                for name in self.__codecs__[codec]["names"]
            ]
            labels = ", ".join(
                localizedString(self.__codecs__[codec]["label"])
                for codec in exclude
            )
        self.logger.info(f"{localizedString(33100)}: {labels}")

    def __stop__(self):
        self.__extractor__ = self.__extractor__.close()
        self.logger.info("stopped")

    def start(self, **kwargs):
        self.logger.info("starting...")
        self.__setup__()
        self.serve(**kwargs)
        self.__stop__()

    def onSettingsChanged(self):
        self.__setup__()

    # --------------------------------------------------------------------------

    def __extract__(self, url, **kwargs):
        return self.__extractor__.extract_info(
            unquote(url), download=False, **kwargs
        )

    def __video_stream__(self, fmt, fps=0, **kwargs):
        fmt_fps = fmt["fps"]
        if ((not fps) or (fmt_fps <= fps)):
            return {
                "lang": None,
                "averageBitrate": int(fmt["vbr"] * 1000),
                "width": fmt["width"],
                "height": fmt["height"],
                "frameRate": fmt_fps
            }

    def __audio_stream__(self, fmt, **kwargs):
        return {
            "lang": fmt["language"],
            "averageBitrate": int(fmt["abr"] * 1000),
            "audioSamplingRate": fmt["asr"],
            "audioChannels": fmt["audio_channels"]
        }

    def __stream__(self, contentType, codecs, fmt, exclude=None, **kwargs):
        if (
            ((not exclude) or (not codecs.startswith(exclude))) and
            (stream := self.__streamTypes__[contentType](fmt, **kwargs))
        ):
            return dict(
                stream,
                contentType=contentType,
                mimeType=f"{contentType}/{fmt['ext']}",
                id=fmt["format_id"],
                codecs=codecs,
                #averageBitrate=int(fmt["tbr"] * 1000),
                url=fmt["url"],
                indexRange=fmt["indexRange"],
                initRange=fmt["initRange"]
            )

    def __streams__(self, formats, **kwargs):
        for fmt in formats:
            if fmt.get("container", "").endswith("_dash"):
                args = None
                vcodec = fmt.get("vcodec")
                acodec = fmt.get("acodec")
                if (vcodec and (vcodec != "none") and (acodec == "none")):
                    args = ("video", vcodec)
                elif (acodec and (acodec != "none") and (vcodec == "none")):
                    args = ("audio", acodec)
                if args and (stream := self.__stream__(*args, fmt, **kwargs)):
                    yield stream

    def __subtitles__(self, subtitles):
        for lang, subs in subtitles.items():
            for sub in subs:
                if (
                    (id := sub.get("name")) and
                    ((ext := sub["ext"]) in self.__supportedSubtitles__)
                ):
                    yield dict(
                        contentType="text",
                        mimeType=f"text/{ext}",
                        lang=lang,
                        id=id,
                        url=sub["url"]
                    )

    def __manifest__(self, duration, formats, subtitles, **kwargs):
        if (streams := list(self.__streams__(formats, **kwargs))):
            streams.extend(self.__subtitles__(subtitles))
            return self.__manifests__.manifest(duration, streams)

    # public api ---------------------------------------------------------------

    @public
    def video(self, url, captions=False, exclude=None, fps=0, **kwargs):
        self.logger.info(f"video(url={url})")
        captions = captions or self.__captions__
        if (video := YtDlpVideo(self.__extract__(url), captions=captions)):
            formats = video.pop("formats")
            subtitles = video.pop("subtitles")
            if video["url"]:
                video["manifestType"] = "hls"
                video["mimeType"] = None
            else:
                exclude = exclude or self.__exclude__
                fps = fps or self.__fps__
                video["url"] = self.__manifest__(
                    video["duration"],
                    formats,
                    subtitles,
                    exclude=tuple(exclude) if exclude else None,
                    fps=fps,
                    **kwargs
                )
                video["manifestType"] = "mpd"
                video["mimeType"] = "application/dash+xml"
            return video

    @public
    def extract(self, url, **kwargs):
        self.logger.info(f"extract(url={url}, kwargs={kwargs})")
        return self.__extractor__.sanitize_info(self.__extract__(url, **kwargs))


# __main__ ---------------------------------------------------------------------

if __name__ == "__main__":
    YtDlpService().start()
