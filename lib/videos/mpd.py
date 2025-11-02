# -*- coding: utf-8 -*-


from videos import FpsHints, VideoHeights, NoneCodec


# ------------------------------------------------------------------------------

def __video_stream__(fmt, fps_limit=0, fps_hint="int", height=None, **kwargs):
    fps = fmt["fps"]
    if ((not fps_limit) or (fps <= fps_limit)):
        stream = {
            "codecs": fmt["vcodec"],
            "bandwidth": int(fmt["vbr"] * 1000),
            "width": fmt["width"],
            "height": fmt["height"],
            "frameRate": FpsHints[fps_hint]["values"][fps]
        }
        if (
            height and
            (
                (fmt.get("height", 0) == height) or
                (
                    (height := VideoHeights.get(height, {})) and
                    fmt.get("width", 0) == height["width"]
                )
            )

        ):
            stream["default"] = True
        return stream


def __audio_stream__(fmt, inputstream="adaptive", **kwargs):
    stream = {
        "codecs": fmt["acodec"],
        "bandwidth": int(fmt["abr"] * 1000),
        "lang": fmt["language"],
        "audioSamplingRate": fmt["asr"],
        "audioChannels": fmt.get("audio_channels", 2)
    }
    if inputstream == "adaptive": # isa custom attributes
        stream.update(
            original=fmt.get("audioIsOriginal", False),
            #default=fmt.get("audioIsDefault", False),
            impaired=fmt.get("audioIsDescriptive", False)
        )
    return stream


__streamTypes__ = {
    "video": __video_stream__,
    "audio": __audio_stream__
}


# ------------------------------------------------------------------------------

def __include__(contentType, codec, ocodec, exclude):
    if (
        codec and
        (codec != NoneCodec) and
        (ocodec == NoneCodec) and
        (not codec.startswith(exclude))
    ):
        return contentType
        #return (contentType, codec)


def __filter__(vcodec, acodec, exclude):
    return (
        __include__("video", vcodec, acodec, exclude) or
        __include__("audio", acodec, vcodec, exclude)
    )


def __dash__(formats, exclude):
    return (
        fmt for fmt in formats
        if (
            fmt.get("container", "").endswith("_dash") and
            fmt.setdefault(
                "__contentType__",
                __filter__(fmt.get("vcodec"), fmt.get("acodec"), exclude)
            )
            #fmt.setdefault(
            #    "__stream_args__",
            #    __filter__(fmt.get("vcodec"), fmt.get("acodec"), exclude)
            #)
        )
    )


# streams ----------------------------------------------------------------------

def __streams__(formats, exclude=None, **kwargs):
    for fmt in __dash__(formats, exclude or tuple()):
        contentType = fmt["__contentType__"]
        if (stream := __streamTypes__[contentType](fmt, **kwargs)):
            yield dict(
                stream,
                contentType=contentType,
                mimeType=f"{contentType}/{fmt['ext']}",
                id=fmt["format_id"],
                url=fmt["url"],
                indexRange=fmt.get("indexRange", {}),
                initRange=fmt.get("initRange", {})
            )


def __subtitles__(subtitles):
    return [
        dict(
            contentType="text",
            mimeType=f"text/{subtitle['ext']}",
            lang=subtitle["language"],
            id=subtitle["name"],
            url=subtitle["uri"]
        )
        for subtitle in subtitles
        if (not subtitle["protocol"])
    ]


def streams(video, formats, subtitles, **kwargs):
    if (streams := list(__streams__(formats, **kwargs))):
        streams.extend(__subtitles__(subtitles))
    return (video["duration"], streams)
