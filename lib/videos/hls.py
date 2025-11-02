# -*- coding: utf-8 -*-


from videos import languages, NoneCodec


# streams ----------------------------------------------------------------------

def __subtitles__(subtitles):
    return [
        dict(
            language=subtitle["language"],
            name=subtitle["name"],
            uri=subtitle["uri"]
        )
        for subtitle in subtitles
        if (subtitle["protocol"] == "m3u8_native")
    ]


def streams(video, formats, subtitles, **kwargs):
    streams = []
    groups = {group_type: {} for group_type in ("video", "audio")}
    subtitles = __subtitles__(subtitles)
    for f in formats:
        if f.get("protocol", "") == "m3u8_native":
            vcodec = (
                ((vcodec := f.get("vcodec", NoneCodec)) != NoneCodec) and vcodec
            )
            acodec = (
                ((acodec := f.get("acodec", NoneCodec)) != NoneCodec) and acodec
            )
            if (codecs := [codec for codec in (vcodec, acodec) if codec]):
                stream = {
                    "codecs": ",".join(codecs),
                    "bandwidth": f["tbr"] * 1000,
                    "url": f["url"]
                }
                if (vcodec and (resolution := f.get("resolution"))):
                    stream["resolution"] = resolution
                    if (fps := f.get("fps")):
                        stream["frame_rate"] = fps
                        resolution = f"{resolution}@{int(fps)}"
                    groups["video"][resolution] = {"name": resolution} # setdefault?
                    stream["video"] = resolution
                if (
                    acodec and
                    (language := f.get("language")) and
                    (name := languages.language_name(language))
                ):
                    groups["audio"][language] = { # setdefault?
                        "name": name, "language": language
                    }
                    stream["audio"] = language
                if subtitles:
                    stream["subtitles"] = "subtitles"
                streams.append(stream)
    return (streams, groups, subtitles)
