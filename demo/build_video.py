import json, subprocess, re, glob
exec(open('narr.py').read()); D = json.load(open('dur.json')); PAD = 0.7
def sh(*a): subprocess.run(list(a), check=True, capture_output=True)
def probe(f): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]))
V = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
def img(name, imgs, k):
    T = D[k] + PAD; per = T / len(imgs); parts = []
    for i, im in enumerate(imgs):
        o = f"p_{name}_{i}.mp4"; sh("ffmpeg","-y","-loop","1","-t",f"{per:.3f}","-i",im,"-vf",V,"-c:v","libx264","-preset","veryfast","-crf","22",o); parts.append(o)
    return concat_v(parts, f"v_{name}.mp4")
def concat_v(parts, out):
    open("l.txt","w").write("".join(f"file '{p}'\n" for p in parts)); sh("ffmpeg","-y","-f","concat","-safe","0","-i","l.txt","-c","copy",out); return out
def clip(name, src, start, length, target, label=None):
    speed = length / target; vf = f"trim=start={start}:duration={length},setpts=(PTS-STARTPTS)/{speed},{V}"
    if label: vf += f",drawtext=text='{label}':x=w-tw-24:y=24:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8"
    o = f"v_{name}.mp4"; sh("ffmpeg","-y","-i",src,"-vf",vf,"-an","-t",f"{target:.3f}","-c:v","libx264","-preset","veryfast","-crf","22",o); return o
src = glob.glob("vid_app/*.webm")[0]; L = probe(src); m = dict(l.split() for l in open("marks.txt"))
end = float(m["end"]); click = L - (end - float(m["click"])); done = L - (end - float(m["done"]))
segs = []
segs.append(img("title", ["s-01.png"], "title")); segs.append(img("problem", ["s-02.png"], "problem"))
segs.append(img("zetaris", ["zet1.png", "zet2.png"], "zetaris"))
segs.append(clip("ask", src, max(0, click - (D["ask"] + PAD)), D["ask"] + PAD, D["ask"] + PAD))
run_len = done - click; spd = run_len / (D["run"] + PAD)
segs.append(clip("run", src, click, run_len, D["run"] + PAD, label=f"real run - sped up {spd:.0f}x ({run_len/60:.1f} min)"))
segs.append(clip("report", src, done, L - done, D["report"] + PAD, label="real speed" if (L-done) <= D["report"]+PAD+0.5 else "scroll sped up"))
segs.append(img("trust", ["s-06.png"], "trust")); segs.append(img("results", ["s-08.png"], "results"))
segs.append(img("arch", ["s-05.png", "s-07.png"], "arch")); segs.append(img("end", ["s-10.png"], "end"))
# make every segment exactly narration+PAD, then audio
fixed = []
for (k, _), v in zip(SEG, segs):
    T = D[k] + PAD; o = f"f_{k}.mp4"
    sh("ffmpeg","-y","-i",v,"-i",f"a_{k}.wav","-filter_complex",f"[0:v]tpad=stop_mode=clone:stop_duration=5,trim=duration={T:.3f}[v];[1:a]apad,atrim=duration={T:.3f},aresample=44100[a]","-map","[v]","-map","[a]","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","128k",o)
    fixed.append(o)
concat_v(fixed, "joined.mp4")
# captions: split sentences, time by character share
def ts(t): h=int(t//3600); mm=int(t%3600//60); s=t%60; return f"{h:02d}:{mm:02d}:{s:06.3f}".replace(".", ",")
srt=[]; t0=0; n=1
for k, text in SEG:
    sents=[s for s in re.split(r"(?<=[.?!:])\s+", text) if s]; tot=sum(len(s) for s in sents); t=t0
    for s in sents:
        d = D[k]*len(s)/tot; srt.append(f"{n}\n{ts(t)} --> {ts(t+d)}\n{s}\n"); n+=1; t+=d
    t0 += D[k]+PAD
open("captions.srt","w").write("\n".join(srt))
sh("ffmpeg","-y","-i","joined.mp4","-vf","subtitles=captions.srt:force_style='FontSize=18,MarginV=22,BorderStyle=3,OutlineColour=&H80000000,Outline=2'","-c:v","libx264","-preset","medium","-crf","23","-c:a","copy","-movflags","+faststart","/workspace/hackathon/whydrop/demo/whydrop_demo.mp4")
print("ok", spd)
