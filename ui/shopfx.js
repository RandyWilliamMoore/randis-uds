// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
const SFX = (function () { const SFX = {};
SFX.FX={
  eq:{l:'Equalizer',p:{low:[0,-18,18,.5,'Low (250 Hz)','dB'],mid:[0,-18,18,.5,'Mid','dB'],midF:[1500,300,6000,10,'Mid frequency','Hz'],high:[0,-18,18,.5,'High (5 kHz)','dB']}},
  filter:{l:'Filter',p:{mode:[['lowpass','highpass','bandpass','notch'],'Type'],freq:[3000,50,12000,10,'Frequency','Hz'],q:[.7,.1,20,.1,'Resonance']}},
  pitch:{l:'Pitch shifter',p:{semi:[0,-24,24,.1,'Shift','st'],mix:[1,0,1,.01,'Mix']}},
  ring:{l:'Robot (ring mod)',p:{freq:[60,1,2000,1,'Frequency','Hz'],mix:[.6,0,1,.01,'Mix']}},
  crush:{l:'Bit crusher',p:{bits:[8,1,16,1,'Bits'],down:[2,1,32,1,'Downsample'],mix:[1,0,1,.01,'Mix']}},
  drive:{l:'Distortion',p:{amount:[.3,0,1,.01,'Drive'],mix:[1,0,1,.01,'Mix']}},
  chorus:{l:'Chorus',p:{rate:[.8,.05,8,.01,'Rate','Hz'],depth:[6,.5,25,.1,'Depth','ms'],mix:[.5,0,1,.01,'Mix']}},
  flanger:{l:'Flanger',p:{rate:[.3,.05,5,.01,'Rate','Hz'],depth:[3,.2,10,.1,'Depth','ms'],fb:[.6,0,.95,.01,'Feedback'],mix:[.5,0,1,.01,'Mix']}},
  tremolo:{l:'Tremolo',p:{rate:[6,.1,30,.1,'Rate','Hz'],depth:[.5,0,1,.01,'Depth']}},
  echo:{l:'Echo',p:{time:[250,10,1500,1,'Time','ms'],fb:[.35,0,.95,.01,'Repeats'],mix:[.3,0,1,.01,'Level']}},
  reverb:{l:'Reverb',p:{size:[.6,0,1,.01,'Room size'],damp:[.4,0,1,.01,'Damping'],mix:[.25,0,1,.01,'Mix']}},
  radio:{l:'Radio / phone',p:{low:[300,50,2000,10,'Low cut','Hz'],high:[3400,800,8000,10,'High cut','Hz'],grit:[.3,0,1,.01,'Grit'],noise:[.02,0,.2,.001,'Static']}},
  comp:{l:'Compressor',p:{thresh:[-18,-60,0,.5,'Threshold','dB'],ratio:[4,1,20,.1,'Ratio'],makeup:[6,0,24,.5,'Makeup','dB']}},
  gain:{l:'Gain',p:{db:[0,-24,24,.5,'Gain','dB']}}
};
SFX.fxDefaults=function(type){var d={type:type,on:true},p=(SFX.FX[type]||{p:{}}).p;for(var k in p){var v=p[k][0];d[k]=Array.isArray(v)?v[0]:v}return d};
function biq(type,f,q,g,sr){var A=Math.pow(10,g/40),w=2*Math.PI*Math.min(Math.max(f,10),sr*.49)/sr,cs=Math.cos(w),sn=Math.sin(w),al=sn/(2*q),b0,b1,b2,a0,a1,a2,s;
  switch(type){case 'lowpass':b0=(1-cs)/2;b1=1-cs;b2=b0;a0=1+al;a1=-2*cs;a2=1-al;break;case 'highpass':b0=(1+cs)/2;b1=-(1+cs);b2=b0;a0=1+al;a1=-2*cs;a2=1-al;break;
    case 'bandpass':b0=al;b1=0;b2=-al;a0=1+al;a1=-2*cs;a2=1-al;break;case 'notch':b0=1;b1=-2*cs;b2=1;a0=1+al;a1=-2*cs;a2=1-al;break;
    case 'peak':b0=1+al*A;b1=-2*cs;b2=1-al*A;a0=1+al/A;a1=-2*cs;a2=1-al/A;break;
    case 'lowshelf':s=2*Math.sqrt(A)*al;b0=A*((A+1)-(A-1)*cs+s);b1=2*A*((A-1)-(A+1)*cs);b2=A*((A+1)-(A-1)*cs-s);a0=(A+1)+(A-1)*cs+s;a1=-2*((A-1)+(A+1)*cs);a2=(A+1)+(A-1)*cs-s;break;
    default:s=2*Math.sqrt(A)*al;b0=A*((A+1)+(A-1)*cs+s);b1=-2*A*((A-1)+(A+1)*cs);b2=A*((A+1)+(A-1)*cs-s);a0=(A+1)-(A-1)*cs+s;a1=2*((A-1)-(A+1)*cs);a2=(A+1)-(A-1)*cs-s}
  b0/=a0;b1/=a0;b2/=a0;a1/=a0;a2/=a0;var x1=0,x2=0,z1=0,z2=0;
  return function(x){var y=b0*x+b1*x1+b2*x2-a1*z1-a2*z2;x2=x1;x1=x;z2=z1;z1=y;return y}}
function dline(n){var L=n+4,b=new Float32Array(L),w=0;return{push:function(x){b[w]=x;w=(w+1)%L},read:function(d){var r=w-1-d;while(r<0)r+=L;var i=Math.floor(r),f=r-i;return b[i%L]*(1-f)+b[(i+1)%L]*f}}}
SFX.fxProc=function(fx,sr){var q=Object.assign(SFX.fxDefaults(fx.type),fx),mx=function(a,b,m){return a*(1-m)+b*m},t=0,w;
  switch(fx.type){
    case 'eq':{var e1=biq('lowshelf',250,.707,q.low,sr),e2=biq('peak',q.midF,1,q.mid,sr),e3=biq('highshelf',5000,.707,q.high,sr);return function(x){return e3(e2(e1(x)))}}
    case 'filter':return biq(q.mode,q.freq,q.q,0,sr);
    case 'pitch':{var ratio=Math.pow(2,q.semi/12),W=Math.round(sr*.06),L=dline(W*2),ph=0;return function(x){L.push(x);ph+=(1-ratio)/W;ph-=Math.floor(ph);var p2=(ph+.5)%1;
      return mx(x,L.read(ph*W)*(.5-.5*Math.cos(2*Math.PI*ph))+L.read(p2*W)*(.5-.5*Math.cos(2*Math.PI*p2)),q.mix)}}
    case 'ring':w=2*Math.PI*q.freq/sr;return function(x){t+=w;if(t>6.283185307)t-=6.283185307;return mx(x,x*Math.sin(t)*1.4,q.mix)};
    case 'crush':{var lv=Math.pow(2,q.bits-1),c=0,hold=0,dn=Math.max(1,Math.round(q.down));return function(x){if(c++%dn===0)hold=Math.round(x*lv)/lv;return mx(x,hold,q.mix)}}
    case 'drive':{var kk=1+q.amount*30,nn=Math.tanh(kk)*Math.sqrt(kk);return function(x){return mx(x,Math.tanh(x*kk)/nn,q.mix)}}
    case 'chorus':{var L2=dline(Math.ceil(sr*.07)),bs=sr*.015,dp=sr*q.depth/2000;w=2*Math.PI*q.rate/sr;return function(x){L2.push(x);t+=w;
      return mx(x,.5*L2.read(bs+dp*(1+Math.sin(t)))+.5*L2.read(bs+dp*(1+Math.sin(t+2.1))),q.mix)}}
    case 'flanger':{var L3=dline(Math.ceil(sr*.03)),dp3=sr*q.depth/1000,fbk=0;w=2*Math.PI*q.rate/sr;return function(x){L3.push(x+fbk*q.fb);t+=w;var y=L3.read(1+dp3*(.5+.5*Math.sin(t)));fbk=y;return x*(1-q.mix*.5)+y*q.mix*.5}}
    case 'tremolo':w=2*Math.PI*q.rate/sr;return function(x){t+=w;return x*(1-q.depth*(.5+.5*Math.sin(t)))};
    case 'echo':{var ne=Math.max(1,Math.round(sr*q.time/1000)),L4=dline(ne+2);return function(x){var d=L4.read(ne-1);L4.push(x+d*q.fb);return x+d*q.mix}}
    case 'reverb':{var s=sr/44100,fk=.7+.27*q.size,dm=q.damp*.45;
      var combs=[1116,1188,1277,1356,1422,1491,1557,1617].map(function(l){return{b:new Float32Array(Math.max(8,Math.round(l*s*(.45+q.size*.75)))),i:0,f:0}});
      var aps=[556,441,341,225].map(function(l){return{b:new Float32Array(Math.max(4,Math.round(l*s))),i:0}});
      return function(x){var o=0,inp=x*.12;for(var j=0;j<8;j++){var cb=combs[j],y=cb.b[cb.i];cb.f=y*(1-dm)+cb.f*dm;cb.b[cb.i]=inp+cb.f*fk;cb.i=(cb.i+1)%cb.b.length;o+=y}
        for(j=0;j<4;j++){var a=aps[j],bo=a.b[a.i];a.b[a.i]=o+bo*.5;o=bo-o;a.i=(a.i+1)%a.b.length}return x*(1-q.mix*.5)+o*q.mix*1.2}}
    case 'radio':{var h1=biq('highpass',q.low,.8,0,sr),h2=biq('highpass',q.low,.8,0,sr),l1=biq('lowpass',q.high,.8,0,sr),l2=biq('lowpass',q.high,.8,0,sr),kr=1+q.grit*8,nr=Math.tanh(kr),seed=12345;
      return function(x){seed=(Math.imul(seed,1103515245)+12345)>>>0;var nz=(seed/4294967296*2-1)*q.noise;return l2(l1(h2(h1(Math.tanh(x*kr)/nr+nz))))}}
    case 'comp':{var env=0,at=Math.exp(-1/(sr*.005)),rl=Math.exp(-1/(sr*.12)),mk=Math.pow(10,q.makeup/20);return function(x){var a=Math.abs(x);env=a>env?at*env+(1-at)*a:rl*env+(1-rl)*a;
      var db=20*Math.log(env+1e-9)/Math.LN10,g=db>q.thresh?Math.pow(10,(q.thresh-db)*(1-1/q.ratio)/20):1;return x*g*mk}}
    case 'gain':{var gg=Math.pow(10,q.db/20);return function(x){return x*gg}}}
  return function(x){return x}};
function fxTail(list){var t=0;(list||[]).forEach(function(f){if(f.on===false)return;var q=Object.assign(SFX.fxDefaults(f.type),f);
  if(f.type==='echo')t+=q.time/1000*Math.min(12,Math.log(.01)/Math.log(Math.max(.05,q.fb))+1);if(f.type==='reverb')t+=.4+2.2*q.size});return Math.min(t,15)}
SFX.applyFx=function(x,list,sr){list=(list||[]).filter(function(f){return f&&f.on!==false&&SFX.FX[f.type]});if(!list.length)return x;
  var tail=Math.round(fxTail(list)*sr),out=new Float32Array(x.length+tail),procs=list.map(function(f){return SFX.fxProc(f,sr)});
  for(var i=0;i<out.length;i++){var v=i<x.length?x[i]:0;for(var j=0;j<procs.length;j++)v=procs[j](v);out[i]=isFinite(v)?v:0}
  var e=out.length;while(e>x.length&&Math.abs(out[e-1])<2e-4)e--;return e<out.length?out.slice(0,e):out};
return SFX; })();
