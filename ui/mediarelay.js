// Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
const MEDIA_SHIM = `<script>(function(){
if(window.__udsMedia)return;window.__udsMedia=1;
var md=navigator.mediaDevices;if(!md){try{md={};Object.defineProperty(navigator,"mediaDevices",{value:md});}catch(x){return;}}
var seq=0,live={},AC=window.AudioContext||window.webkitAudioContext;
function num(v){if(typeof v==="number")return v;if(v&&typeof v==="object")return v.ideal||v.exact||v.max||v.min||0;return 0;}
function done(id){var L=live[id];if(!L)return;var on=L.stream&&L.stream.getTracks().some(function(t){return t.readyState==="live";});
 if(!on){delete live[id];try{L.ac&&L.ac.close();}catch(x){}parent.postMessage({uds:"media-close",id:id},"*");}}
md.getUserMedia=function(c){c=c||{};return new Promise(function(res,rej){
 var id="m"+(++seq)+"_"+Date.now()%100000,wa=!!c.audio,wv=!!c.video,vc=typeof c.video==="object"?c.video:{};
 if(!wa&&!wv)return rej(new TypeError("Ask for audio or video"));
 var L={res:res,rej:rej,wa:wa,wv:wv};live[id]=L;
 if(wa&&AC){try{L.ac=new AC();}catch(x){}}
 parent.postMessage({uds:"media-open",id:id,audio:wa,sr:L.ac?L.ac.sampleRate:0,video:wv?{w:num(vc.width)||640,h:num(vc.height)||480,facing:typeof vc.facingMode==="string"?vc.facingMode:"user"}:false},"*");
 setTimeout(function(){if(live[id]&&!L.stream){delete live[id];try{L.ac&&L.ac.close();}catch(x){}rej(new DOMException("The app did not answer","NotAllowedError"));}},60000);});};
md.enumerateDevices=function(){return Promise.resolve([{kind:"audioinput",deviceId:"default",groupId:"uds",label:"Microphone (through Randis UDS)"},{kind:"videoinput",deviceId:"default",groupId:"uds",label:"Camera (through Randis UDS)"}]);};
addEventListener("message",function(e){var d=e.data;if(e.source!==parent||!d||typeof d.uds!=="string"||d.uds.indexOf("media-")!==0)return;var L=live[d.id];if(!L)return;
 if(d.uds==="media-err"){delete live[d.id];try{L.ac&&L.ac.close();}catch(x){}L.rej(new DOMException(d.msg||"No microphone or camera",d.name||"NotFoundError"));return;}
 if(d.uds==="media-ok"){var tr=[];
  if(L.wa&&L.ac){var ac=L.ac,dest=ac.createMediaStreamDestination(),sp=ac.createScriptProcessor(2048,1,1),q=[],off=0;L.q=q;
   sp.onaudioprocess=function(ev){var o=ev.outputBuffer.getChannelData(0),i=0;while(i<o.length&&q.length){var b=q[0],n=Math.min(o.length-i,b.length-off);o.set(b.subarray(off,off+n),i);i+=n;off+=n;if(off>=b.length){q.shift();off=0;}}for(;i<o.length;i++)o[i]=0;};
   var z=ac.createConstantSource?ac.createConstantSource():null;if(z){var g=ac.createGain();g.gain.value=0;z.connect(g);g.connect(sp);z.start();}
   sp.connect(dest);L.sp=sp;try{ac.resume();}catch(x){}tr=tr.concat(dest.stream.getAudioTracks());}
  if(L.wv){var cv=document.createElement("canvas");cv.width=d.w||640;cv.height=d.h||480;L.g=cv.getContext("2d");tr=tr.concat(cv.captureStream(30).getVideoTracks());}
  L.stream=new MediaStream(tr);
  tr.forEach(function(t){var st=t.stop.bind(t);t.stop=function(){st();setTimeout(function(){done(d.id);},0);};});
  L.res(L.stream);return;}
 if(d.uds==="media-a"&&L.q){L.q.push(d.pcm);if(L.q.length>24)L.q.splice(0,L.q.length-8);return;}
 if(d.uds==="media-v"&&L.g){try{L.g.drawImage(d.bmp,0,0,L.g.canvas.width,L.g.canvas.height);d.bmp.close&&d.bmp.close();}catch(x){}parent.postMessage({uds:"media-vack",id:d.id},"*");}
});
addEventListener("pagehide",function(){Object.keys(live).forEach(function(id){parent.postMessage({uds:"media-close",id:id},"*");});});
})();<\/script>`;
function withMedia(html, on) {
  if (!on) return html;
  html = String(html || "");
  for (const re of [/<head\b[^>]*>/i, /<html\b[^>]*>/i, /^\s*<!doctype[^>]*>/i]) {
    const m = re.exec(html);
    if (m) return html.slice(0, m.index + m[0].length) + MEDIA_SHIM + html.slice(m.index + m[0].length);
  }
  return MEDIA_SHIM + html;
}
const MEDIA_LIVE = {};
function mediaStop(key) {
  const M = MEDIA_LIVE[key]; if (!M) return; delete MEDIA_LIVE[key];
  try { M.st.getTracks().forEach(t => t.stop()); } catch (e) {}
  try { M.ac && M.ac.close(); } catch (e) {}
  clearInterval(M.timer);
  if (!Object.keys(MEDIA_LIVE).some(k => MEDIA_LIVE[k].owner === M.owner)) try { M.mark(false); } catch (e) {}
}
function mediaStopOwner(owner) { Object.keys(MEDIA_LIVE).filter(k => MEDIA_LIVE[k].owner === owner).forEach(mediaStop); }
function mediaRelayStart(find) {
  window.addEventListener("message", async e => {
    const d = e.data; if (!d || typeof d.uds !== "string" || !/^media-(open|close|vack)$/.test(d.uds)) return;
    const T = find(e.source); if (!T || !T.ok) { if (T && d.uds === "media-open") T.post({ uds: "media-err", id: d.id, name: "NotAllowedError", msg: "This tab isn't allowed the microphone or camera." }); return; }
    const key = T.key + ":" + String(d.id).slice(0, 24);
    if (d.uds === "media-close") return mediaStop(key);
    if (d.uds === "media-vack") { if (MEDIA_LIVE[key]) MEDIA_LIVE[key].busy = false; return; }
    const v = d.video && typeof d.video === "object" ? d.video : null, cl = (n, a, b, f) => Math.min(b, Math.max(a, +n || f));
    let st;
    try {
      st = await navigator.mediaDevices.getUserMedia({
        audio: d.audio ? { echoCancellation: false, noiseSuppression: true, autoGainControl: true } : false,
        video: v ? { width: cl(v.w, 160, 1920, 640), height: cl(v.h, 120, 1080, 480), facingMode: v.facing === "environment" ? "environment" : "user" } : false });
    } catch (err) {
      const nf = err && (err.name === "NotFoundError" || err.name === "OverconstrainedError");
      return T.post({ uds: "media-err", id: d.id, name: err && err.name || "NotAllowedError",
        msg: nf ? "No microphone or camera found. Check one is plugged in and turned on in Windows Settings > Privacy > Microphone/Camera."
                : "The microphone or camera was blocked. Allow it when Windows asks, or turn it on in Windows Settings > Privacy > Microphone/Camera (\"Let desktop apps access\")." });
    }
    const M = { st, owner: T.key, mark: T.mark, busy: false };
    MEDIA_LIVE[key] = M; T.mark(true);
    let w = 0, h = 0;
    if (d.audio && st.getAudioTracks().length) {
      const AC = window.AudioContext || window.webkitAudioContext; let ac;
      try { ac = new AC(d.sr ? { sampleRate: d.sr } : undefined); } catch (x) { ac = new AC(); }
      M.ac = ac; try { await ac.resume(); } catch (x) {}
      const src = ac.createMediaStreamSource(st), sp = ac.createScriptProcessor(2048, 1, 1), mute = ac.createGain(); mute.gain.value = 0;
      sp.onaudioprocess = ev => { if (!MEDIA_LIVE[key]) return; const x = new Float32Array(ev.inputBuffer.getChannelData(0)); T.post({ uds: "media-a", id: d.id, pcm: x }, [x.buffer]); };
      src.connect(sp); sp.connect(mute); mute.connect(ac.destination);
    }
    if (v && st.getVideoTracks().length) {
      const vid = document.createElement("video"); vid.muted = true; vid.playsInline = true; vid.srcObject = st;
      try { await vid.play(); } catch (x) {}
      const s = st.getVideoTracks()[0].getSettings ? st.getVideoTracks()[0].getSettings() : {}; w = s.width || vid.videoWidth || 640; h = s.height || vid.videoHeight || 480;
      M.timer = setInterval(async () => {
        if (!MEDIA_LIVE[key] || M.busy || vid.readyState < 2) return; M.busy = true;
        try { const b = await createImageBitmap(vid); T.post({ uds: "media-v", id: d.id, bmp: b }, [b]); } catch (x) { M.busy = false; }
      }, 33);
    }
    T.post({ uds: "media-ok", id: d.id, sr: M.ac ? M.ac.sampleRate : 0, w, h });
  });
}
