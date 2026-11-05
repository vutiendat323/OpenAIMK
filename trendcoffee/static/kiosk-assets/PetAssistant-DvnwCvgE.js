import{n as e,r as t,t as n}from"./index-DALW8B-j.js";var r=t(e(),1),i=()=>a(new Float32Array(16));function a(e){return e.fill(0),e[0]=e[5]=e[10]=e[15]=1,e}function o(e,t,n){let r=new Float32Array(16);for(let e=0;e<4;e++)for(let i=0;i<4;i++)r[e*4+i]=t[i]*n[e*4]+t[4+i]*n[e*4+1]+t[8+i]*n[e*4+2]+t[12+i]*n[e*4+3];return e.set(r),e}function s(e,t,n,r){return a(e),e[12]=t,e[13]=n,e[14]=r,e}function c(e,t,n,r){return a(e),e[0]=t,e[5]=n,e[10]=r,e}function l(e,t,n,r){let i=Math.cos(t),o=Math.sin(t),s=Math.cos(n),c=Math.sin(n),l=Math.cos(r),u=Math.sin(r);return a(e),e[0]=l*s,e[1]=u*s,e[2]=-c,e[4]=l*c*o-u*i,e[5]=u*c*o+l*i,e[6]=s*o,e[8]=l*c*i+u*o,e[9]=u*c*i-l*o,e[10]=s*i,e}function u(e,t,n){let[r,i,o]=t,s=Math.cos(n),c=Math.sin(n),l=1-s;return a(e),e[0]=l*r*r+s,e[1]=l*r*i+c*o,e[2]=l*r*o-c*i,e[4]=l*r*i-c*o,e[5]=l*i*i+s,e[6]=l*i*o+c*r,e[8]=l*r*o+c*i,e[9]=l*i*o-c*r,e[10]=l*o*o+s,e}function d(e,t){let[n,r,i,o,s,c,l,u,d,f,p,m,h,g,_,v]=t,y=n*c-r*s,b=n*l-i*s,x=n*u-o*s,S=r*l-i*c,C=r*u-o*c,w=i*u-o*l,T=d*g-f*h,E=d*_-p*h,D=d*v-m*h,O=f*_-p*g,k=f*v-m*g,A=p*v-m*_,j=y*A-b*k+x*O+S*D-C*E+w*T;if(!j)return a(e);let M=1/j;return e[0]=(c*A-l*k+u*O)*M,e[1]=(i*k-r*A-o*O)*M,e[2]=(g*w-_*C+v*S)*M,e[3]=(p*C-f*w-m*S)*M,e[4]=(l*D-s*A-u*E)*M,e[5]=(n*A-i*D+o*E)*M,e[6]=(_*x-h*w-v*b)*M,e[7]=(d*w-p*x+m*b)*M,e[8]=(s*k-c*D+u*T)*M,e[9]=(r*D-n*k-o*T)*M,e[10]=(h*C-g*x+v*y)*M,e[11]=(f*x-d*C-m*y)*M,e[12]=(c*E-s*O-l*T)*M,e[13]=(n*O-r*E+i*T)*M,e[14]=(g*b-h*S-_*y)*M,e[15]=(d*S-f*b+p*y)*M,e}function f(e,t){let[n,r,i]=t;return[e[0]*n+e[4]*r+e[8]*i+e[12],e[1]*n+e[5]*r+e[9]*i+e[13],e[2]*n+e[6]*r+e[10]*i+e[14]]}function p(e,t){let[n,r,i]=t;return[e[0]*n+e[4]*r+e[8]*i,e[1]*n+e[5]*r+e[9]*i,e[2]*n+e[6]*r+e[10]*i]}var m=(e,t,n)=>Math.min(n,Math.max(t,e)),h=(e,t,n)=>e+(t-e)*n,g=(e,t,n)=>{let r=m((n-e)/(t-e),0,1);return r*r*(3-2*r)},_=e=>e<.5?4*e*e*e:1-(-2*e+2)**3/2;function v(e){let t=Math.floor(e*4294967295)>>>0||1;return()=>{t=t+1831565813>>>0;let e=t;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}}var y=class{constructor(e=0){this.x=e}x;v=0;step(e,t,n,r){let i=n*Math.PI*2;return this.v+=(i*i*(e-this.x)-2*r*i*this.v)*t,this.x+=this.v*t,this.x}},b=[{round:0,open:1,weight:.34},{round:.08,open:.55,weight:.26},{round:.7,open:.85,weight:.24},{round:1,open:.5,weight:.16}],x=class{constructor(e){this.random=e,this.silence=.15+e()*.3}random;open=0;round=0;age=0;length=0;stress=0;silence=0;syllablesLeft=0;wordsLeft=0;reset(){this.age=this.length=this.open=0,this.syllablesLeft=this.wordsLeft=0,this.silence=.12}update(e){if(this.silence>0){this.silence-=e,this.open=0;return}this.age+=e,this.age>=this.length&&this.next();let t=m(this.age/this.length,0,1);this.open=this.stress*Math.sin(Math.PI*t)**.55}next(){let e=this.random;this.age=0;let t=this.syllablesLeft===0;t&&(this.wordsLeft===0?(this.wordsLeft=3+Math.floor(e()*5),this.silence=this.length>0?.45+e()*.7:0):this.silence=.04+e()*.09,this.wordsLeft--,this.syllablesLeft=1+Math.floor(e()**1.6*3)),this.syllablesLeft--;let n=t&&e()<.6,r=S(b,e());this.length=.12+e()*.13,this.stress=r.open*(n?.85+e()*.15:.5+e()*.35),this.round=r.round}};function S(e,t){for(let n of e){if(t<n.weight)return n;t-=n.weight}return e[0]}var C=[`idle`,`thinking`,`listening`,`speaking`,`sleeping`,`working`,`error`,`surprised`,`celebrating`,`sad`],w=[...C,`happy`],T=Object.fromEntries(w.map((e,t)=>[e,t])),E={idle:{lid:.06,squint:0,smile:.35,tilt:0,energy:1,flap:.05,glow:[.45,.7,1],exposure:1,wide:0,asym:0},thinking:{lid:.4,squint:0,smile:-.15,tilt:.22,energy:.6,flap:0,glow:[1,.55,.12],exposure:1,wide:0,asym:0},listening:{lid:0,squint:0,smile:.2,tilt:-.08,energy:.8,flap:.05,glow:[.25,1,.5],exposure:1,wide:.15,asym:0},speaking:{lid:.04,squint:.1,smile:.45,tilt:0,energy:1.2,flap:.1,glow:[.35,.82,1],exposure:1,wide:0,asym:0},sleeping:{lid:1,squint:0,smile:0,tilt:0,energy:.35,flap:0,glow:[.08,.09,.18],exposure:.84,wide:0,asym:0},working:{lid:.3,squint:.2,smile:.05,tilt:0,energy:1.3,flap:.18,glow:[.6,.45,1],exposure:1,wide:0,asym:0},error:{lid:.12,squint:.15,smile:-.45,tilt:.1,energy:.9,flap:.25,glow:[1,.16,.12],exposure:.97,wide:.2,asym:1},surprised:{lid:0,squint:0,smile:0,tilt:0,energy:1,flap:.55,glow:[.95,.95,1],exposure:1.04,wide:1,asym:0},celebrating:{lid:0,squint:1,smile:1,tilt:0,energy:1.8,flap:.9,glow:[1,.72,.2],exposure:1.08,wide:0,asym:0},sad:{lid:.42,squint:0,smile:-.85,tilt:-.32,energy:.35,flap:-.12,glow:[.22,.32,.7],exposure:.9,wide:0,asym:0},happy:{lid:0,squint:1,smile:1,tilt:0,energy:1.6,flap:.3,glow:[1,.42,.72],exposure:1.05,wide:0,asym:0}},D={float:0,hop:.16,squash:1,snap:1,look:1,snapLook:0,talkSquash:0},O=.11,k=1.8,A=class{temperament;state=`idle`;pointer=null;shown=`idle`;previous=`idle`;switched=10;time=0;since=0;random;yaw=new y;pitch=new y;roll=new y;squash=new y;hover;face={lid:new y,squint:new y,smile:new y(.3),tilt:new y,talk:new y,round:new y,gazeX:new y,gazeY:new y,flap:new y,energy:new y(1),exposure:new y(1),wide:new y,asym:new y};weights;glow=[...E.idle.glow];jump=null;look={yaw:0,pitch:0,x:0,y:0};saccade={x:0,y:0,next:0};nextLook=.6;nextBlink;blinkAge=-1;nextHop;nextSide=4;side=1;nextNod=2.5;shake={start:-10,amount:0,next:0};sigh={start:-10,next:0};reactUntil=-1;speech;lastTalk=0;syllableArmed=!0;matrices={a:i(),b:i()};pose;constructor(e={},t=.5){this.temperament={...D,...e},this.random=v(t),this.speech=new x(this.random),this.nextBlink=1+this.random()*3,this.nextHop=6+this.random()*6,this.hover=new y(this.temperament.float),this.weights=Object.fromEntries(w.map(e=>[e,new y(+(e===`idle`))])),this.pose={root:i(),minScale:1,lift:0,channels:{yaw:0,pitch:0,roll:0,flap:0,talk:0,energy:1},weights:Object.fromEntries(w.map(e=>[e,+(e===`idle`)])),expression:`idle`,faceA:[0,0,0,0],faceB:[0,0,0,0],faceC:[0,0,1,0],faceD:[0,0,0,0],glow:this.glow,exposure:1,events:[]}}setState(e){e!==this.state&&(this.state=e,this.since=0,e===`speaking`&&this.speech.reset(),this.nextLook=0)}poke(){this.hop(this.temperament.hop*1.5,this.random()<.5?1:-1),this.reactUntil=this.time+k}update(e){if(!(e>0))return;let t=Math.max(1,Math.ceil(e/(1/120)));for(let n=0;n<t;n++)this.step(e/t)}enter(e,t){let n=this.temperament;e===`surprised`?(this.hop(n.hop*.6,0),this.pitch.v+=1.2,this.startShake(t,.35,1/0)):e===`error`?(this.side=this.random()<.5?1:-1,this.squash.v-=2.5,this.startShake(t,1,t+2+this.random())):e===`celebrating`?this.nextHop=t:e===`sad`&&(this.sigh.next=t+1.2)}startShake(e,t,n){this.shake.start=e,this.shake.amount=t,this.shake.next=n}hop(e,t){if(this.jump)return;let n=this.temperament.float>0;this.jump={age:n?O:0,height:e,spin:t,lean:(this.random()-.5)*.3,air:.42+e*.45+(n?.25:0),landed:!1}}step(e){this.time+=e,this.since+=e,this.switched+=e;let t=this.time,n=this.random,r=this.temperament,i=this.pose.events,a=t<this.reactUntil?`happy`:this.state;a!==this.shown&&(this.previous=this.shown,this.shown=a,this.switched=0,i.push(`enter:${a}`),this.enter(a,t));let u=E[a];t>this.nextLook&&(this.look.yaw=(n()-.5)*.75,this.look.pitch=(n()-.5)*.24,this.look.x=m(this.look.yaw*2.2,-1,1),this.look.y=n()<.3?.6:n()<.2?-.6:0,this.nextLook=t+h(1.4+n()*2.6,.45+n()*1.1,r.snapLook)),t>this.saccade.next&&(this.saccade.x=(n()-.5)*.22,this.saccade.y=(n()-.5)*.14,this.saccade.next=t+.25+n()*.7);let d=0,f=0,p=0,g=Math.sin(t*1.9)*.008,v=0,y=0,b=0,x=0,S=u.flap,C=1.3,D=.62,k=r.float,A=this.pointer,j=A&&(a===`idle`||a===`listening`||a===`speaking`||a===`surprised`);switch(a){case`idle`:d=this.look.yaw,f=this.look.pitch,p=-this.look.yaw*.16,v=this.look.x,y=this.look.y,t>this.nextHop&&(this.hop(r.hop*(.9+n()*.4),n()<.35?n()<.5?1:-1:0),this.nextHop=t+7+n()*7);break;case`thinking`:{t>this.nextSide&&(this.side=-this.side,this.nextSide=t+3+n()*2);let e=this.side;d=.24*e+Math.sin(t*.9)*.05,f=.17+Math.sin(t*1.3)*.03,p=-.13*e,v=.7*e,y=.8,C=.9;break}case`listening`:d=-.14,f=.02,p=.17,v=-.2,t>this.nextNod&&(this.pitch.v-=.9,this.nextNod=t+2+n()*2.5);break;case`speaking`:d=Math.sin(t*.7)*.12,p=Math.sin(t*.9)*.05,this.speech.update(e),b=this.speech.open,x=this.speech.round,f=.04+b*.07,g+=b*.014,S+=Math.sin(t*2.6)*.1,C=1.8;break;case`sleeping`:f=-.3,p=.13,d=.06,g=Math.sin(t*1.15)*.016,b=.12+.1*Math.sin(t*1.15),x=.7,k*=.65,C=.55,D=.9,t>this.nextNod&&(this.pitch.v-=.5,this.nextNod=t+5+n()*4);break;case`working`:d=Math.sin(t*.8)*.07,f=-.13+Math.abs(Math.sin(t*5.2))*.03,p=Math.sin(t*.6)*.04,v=Math.sin(t*1.6)*.45,y=-.55,S+=Math.sin(t*11)*.06,C=1.6;break;case`error`:{t>this.shake.next&&this.startShake(t,.55,2.4+n()*1.4);let e=this.side;p=.16*e,d=-.1*e,f=.05,v=.45*e,y=.3,b=.16,C=1.5;break}case`surprised`:f=.1,b=.42,x=1,C=2.2,D=.5;break;case`celebrating`:d=Math.sin(t*3.1)*.22,p=Math.sin(t*6.2)*.1,f=.14,b=.6+.12*Math.sin(t*7),x=.05,S+=Math.sin(t*9)*.25,C=2,t>this.nextHop&&(this.hop(r.hop*1.25,n()<.3?n()<.5?1:-1:0),this.nextHop=t+.85+n()*.4);break;case`sad`:{t>this.sigh.next&&(this.sigh.start=t,this.sigh.next=t+4+n()*2.5);let e=Math.sin(m((t-this.sigh.start)/1.7,0,1)*Math.PI);f=-.24+e*.1,d=Math.sin(t*.3)*.1,p=.08,v=-.15,y=-.65+e*.3,g+=e*.018,k*=.7,C=.7,D=.85;break}case`happy`:d=Math.sin(t*2.2)*.18,p=Math.sin(t*4.4)*.12,f=.12,b=.5+.15*Math.sin(t*8),x=.2,t>this.nextHop&&(this.hop(r.hop*1.05,0),this.nextHop=t+1.05+n()*.4)}j&&A&&(d=m(A.x,-1,1)*.55,f=m(-A.y,-1,1)*.32+(a===`speaking`?b*.07:0),p=-d*.12+(a===`listening`?.12:0),v=m(A.x*2,-1,1),y=m(-A.y*1.5,-1,1)),a!==`sleeping`&&(v+=this.saccade.x,y+=this.saccade.y),r.float>0&&(g+=Math.sin(t*1.5)*.035);let M=h(C,C*3.2,r.snapLook)*r.snap,N=h(D,.95,r.snapLook);this.yaw.step(d*r.look,e,M,N),this.pitch.step(f*r.look,e,M,N),this.roll.step(p,e,C*r.snap,D),this.hover.step(k,e,.6,.8);let P=this.face;P.lid.step(u.lid,e,2.2,.9),P.squint.step(u.squint,e,3,.8),P.smile.step(u.smile,e,2.4,.75),P.tilt.step(u.tilt*this.side,e,1.6,.8),P.talk.step(b,e,14,.8),P.round.step(x,e,6,.8),P.gazeX.step(v,e,7,.85),P.gazeY.step(y,e,7,.85),P.flap.step(S,e,2.4*r.snap,.5),P.energy.step(u.energy,e,.8,1),P.exposure.step(u.exposure,e,.4,1),P.wide.step(u.wide,e,5,.6),P.asym.step(u.asym*this.side,e,3,.8);for(let t of w)this.weights[t].step(+(t===a),e,1.6*r.snap,.95);let ee=1-Math.exp(-e*4),te=a===`thinking`?.55+.45*Math.sin(t*4.2):a===`speaking`?.6+.6*P.talk.x:a===`working`?.75+.25*Math.sin(t*7):a===`error`?Math.sin(t*7)>0?1.1:.45:1;for(let e=0;e<3;e++)this.glow[e]=h(this.glow[e],u.glow[e]*te,ee);this.syllableArmed&&P.talk.x>.55&&this.lastTalk<=.55&&a===`speaking`&&(i.push(`syllable`),this.syllableArmed=!1),P.talk.x<.35&&(this.syllableArmed=!0),this.lastTalk=P.talk.x;let F=0,I=0,L=0,R=0,z=this.jump;if(z){if(z.age+=e,z.age<O)R=.14;else{let e=(z.age-O)/z.air;e<1?(e<.06&&this.squash.x>.05&&(this.squash.v=-2.6),F=4*z.height*e*(1-e),I=z.spin*Math.PI*2*_(m(e*1.08,0,1)),L=z.lean*Math.sin(e*Math.PI),R=e<.5?-.05:0):z.landed?z.age-O-z.air>.35&&(this.jump=null):(z.landed=!0,r.float===0&&(this.squash.v+=3.2,i.push(`land`)))}}r.float>0&&(R*=.3),this.squash.step(R,e,3.2,.32),t>this.nextBlink&&(this.blinkAge=0,this.nextBlink=t+2.2+n()*3.5,n()<.2&&(this.nextBlink=t+.35));let B=0;this.blinkAge>=0&&(this.blinkAge+=e,B=Math.sin(m(this.blinkAge/.17,0,1)*Math.PI),this.blinkAge>.17&&(this.blinkAge=-1));let V=a===`sleeping`,H=Math.sin(t*(V?1.15:2.1))*(V?.024:.01),U=this.squash.x*r.squash+P.talk.x*.05*r.talkSquash,W=1+U*.55-H*.5,G=1-U+H,K=F+g+this.hover.x,{a:ne,b:re}=this.matrices,q=this.pose.root;s(q,0,K,0),o(q,q,l(ne,0,I,L)),o(q,q,c(re,W,G,W));let J=this.pose;J.minScale=Math.min(W,G),J.lift=K,J.expression=a;let Y=J.channels,X=this.shake.amount*Math.max(0,1-(t-this.shake.start)/.6);Y.yaw=this.yaw.x+Math.sin(t*31)*.06*X,Y.pitch=this.pitch.x,Y.roll=this.roll.x+Math.sin(t*38)*.07*X,Y.flap=P.flap.x,Y.talk=P.talk.x,Y.energy=P.energy.x;let ie=0;for(let e of w)ie+=Math.max(0,this.weights[e].x);for(let e of w)J.weights[e]=Math.max(0,this.weights[e].x)/(ie||1);J.faceA=[V?0:B,P.lid.x,P.squint.x,P.smile.x],J.faceB=[P.talk.x,P.gazeX.x,P.gazeY.x,P.tilt.x],J.faceC=[T[this.shown],T[this.previous],m(this.switched/.35,0,1),this.switched<.3?1-this.switched/.3:0],J.faceD=[this.since,P.round.x,P.wide.x,P.asym.x],J.exposure=P.exposure.x}},j=32,M={z:0,bubble:1,sparkle:2,heart:3,note:4,arc:5,puff:6,ring:7,drop:8,spark:9,mote:10,feather:11,dot:12,exclaim:13,warning:14,confetti:15,cloud:16,star:17,gear:18},N={sleeping:[{glyph:`z`,anchor:`top`,rate:.55,offset:[.12,.04,.05],spread:.02,velocity:[.07,.13,0],jitter:.015,wobble:.05,life:[3,3.6],size:[.045,.12],rotation:-.2,spin:.12,color:`#7f88ad`}],thinking:[{glyph:`dot`,anchor:`top`,rate:1.1,offset:[.16,.02,.06],spread:.01,velocity:[.05,.11,0],jitter:.01,wobble:.02,life:[1.5,1.8],size:[.012,.04],color:`#a3abc9`}],listening:[{glyph:`arc`,anchor:`ear`,rate:1.5,offset:[-.4,0,.04],velocity:[.3,0,0],life:[1.05,1.2],size:[.1,.05],rotation:0,color:`#5cc489`}],syllable:[{glyph:`arc`,anchor:`mouth`,rate:2,offset:[.1,0,.06],mirror:!0,velocity:[.24,.02,.04],jitter:.02,life:[.55,.7],size:[.03,.085],rotation:0,color:`#6aaee6`}],"enter:happy":[{glyph:`sparkle`,anchor:`top`,rate:7,spread:.22,velocity:[0,.3,.05],jitter:.4,gravity:.5,drag:1.5,life:[.7,1.1],size:[.06,0],spin:2.4,color:`#ffc94d`},{glyph:`heart`,anchor:`top`,rate:2,spread:.12,velocity:[0,.32,.05],jitter:.15,wobble:.06,life:[1,1.3],size:[.045,.08],color:`#ff6b8f`}],happy:[{glyph:`sparkle`,anchor:`top`,rate:2.5,spread:.35,velocity:[0,.14,0],jitter:.1,life:[.6,.9],size:[.045,0],spin:1.6,color:`#ffd166`}],working:[{glyph:`gear`,anchor:`top`,rate:.7,offset:[.12,.02,.05],spread:.03,velocity:[.05,.1,0],jitter:.02,wobble:.02,life:[2,2.4],size:[.035,.065],spin:2.2,color:`#a99cf0`},{glyph:`dot`,anchor:`top`,rate:2.2,offset:[-.16,.06,.05],spread:.02,velocity:[-.06,.14,0],jitter:.03,life:[.8,1.1],size:[.015,.006],color:`#c7bfff`,glow:!0}],"enter:error":[{glyph:`warning`,anchor:`top`,rate:1,offset:[.02,.12,.08],velocity:[0,.16,0],drag:2.2,life:[1.5,1.5],size:[.12,.1],color:`#ff4d3d`},{glyph:`spark`,anchor:`top`,rate:6,offset:[0,0,.05],velocity:[0,.4,0],jitter:1.3,gravity:1.6,life:[.25,.4],size:[.035,.015],color:`#ffd166`,glow:!0,align:!0}],error:[{glyph:`puff`,anchor:`top`,rate:2.2,offset:[.02,.02,0],spread:.04,velocity:[0,.16,0],jitter:.05,wobble:.04,drag:.4,life:[1.3,1.7],size:[.04,.13],color:`#8b8fa3`}],"enter:surprised":[{glyph:`exclaim`,anchor:`top`,rate:1,offset:[.04,.14,.06],velocity:[0,.3,0],drag:3.5,life:[1.1,1.1],size:[.11,.08],rotation:-.15,color:`#ffcc33`},{glyph:`spark`,anchor:`top`,rate:8,offset:[0,.02,.04],spread:.04,velocity:[0,.5,0],jitter:1.1,drag:4,life:[.3,.42],size:[.05,.02],color:`#ffe08a`,align:!0}],celebrating:[{glyph:`confetti`,anchor:`top`,rate:2.6,spread:.25,velocity:[0,.7,.05],jitter:.7,gravity:.9,drag:1.4,wobble:.06,life:[1.6,2.2],size:[.03,.026],spin:7,color:`#ff5d8f`},{glyph:`confetti`,anchor:`top`,rate:2.6,spread:.25,velocity:[0,.7,.05],jitter:.7,gravity:.9,drag:1.4,wobble:.06,life:[1.6,2.2],size:[.03,.026],spin:-6,color:`#ffc933`},{glyph:`confetti`,anchor:`top`,rate:2.6,spread:.25,velocity:[0,.7,.05],jitter:.7,gravity:.9,drag:1.4,wobble:.06,life:[1.6,2.2],size:[.03,.026],spin:8,color:`#4dc3ff`},{glyph:`confetti`,anchor:`top`,rate:2.6,spread:.25,velocity:[0,.7,.05],jitter:.7,gravity:.9,drag:1.4,wobble:.06,life:[1.6,2.2],size:[.03,.026],spin:-7,color:`#5ee08f`}],"enter:celebrating":[{glyph:`star`,anchor:`top`,rate:6,spread:.1,velocity:[0,.55,.05],jitter:.9,gravity:.6,drag:1.6,life:[.8,1.2],size:[.06,.02],spin:2,color:`#ffd23f`}],sad:[{glyph:`cloud`,anchor:`top`,rate:.42,offset:[-.12,.22,.02],velocity:[0,0,0],wobble:.015,life:[2.6,2.6],size:[.15,.15],color:`#9aa3bd`},{glyph:`drop`,anchor:`top`,rate:4,offset:[-.12,.16,.03],spread:.08,velocity:[0,-.25,0],gravity:1.2,life:[.45,.6],size:[.018,.014],color:`#6aa8ff`,align:!0}],land:[{glyph:`puff`,anchor:`feet`,rate:7,spread:.1,velocity:[0,.05,0],jitter:.32,drag:3.5,life:[.45,.7],size:[.05,.12],color:`#c4cad9`}]};function P(e){let t=parseInt(e.replace(`#`,``),16);return[(t>>16&255)/255,(t>>8&255)/255,(t&255)/255]}function ee(e,t){return e===`drop`?Math.atan2(t[0],-t[1]):Math.atan2(t[1],t[0])}var te=class{constructor(e,t){this.character=e,this.random=t;let n=e.spec.fx??{},r=new Set([...Object.keys(N),...Object.keys(n)].filter(e=>e!==`replace`));for(let t of r){let r=n[t]??[],i=n.replace?.includes(t)?r:[...N[t]??[],...r];this.emitters[t]=i.filter(t=>e.anchors[t.anchor])}}character;random;a=new Float32Array(j*4);b=new Float32Array(j*4);c=new Float32Array(j*4);count=0;emitters={};carry=new Map;particles=[];update(e,t,n){for(let r of this.emitters[t.expression]??[])this.emitContinuous(r,e*t.weights[t.expression],n);for(let t of this.emitters.ambient??[])this.emitContinuous(t,e,n);for(let e of t.events)for(let t of this.emitters[e]??[])this.burst(t,t.rate,n);let r=[];for(let t of this.particles){if(t.age+=e,t.age>=t.life)continue;let n=t.spec;t.vel[1]-=(n.gravity??0)*e;let i=Math.max(0,1-(n.drag??0)*e);for(let n=0;n<3;n++)t.vel[n]*=i,t.pos[n]+=t.vel[n]*e;n.wobble&&(t.pos[0]+=Math.cos(t.age*3.1+t.seed*6.28)*n.wobble*e*3),t.rot=n.align?ee(n.glyph,t.vel):t.rot+(n.spin??0)*e,r.push(t)}this.particles=r.slice(-j),this.pack()}emitContinuous(e,t,n){let r=(this.carry.get(e)??this.random())+e.rate*t,i=Math.floor(r);this.carry.set(e,r-i),i>0&&this.burst(e,i,n)}burst(e,t,n){let r=this.character.anchors[e.anchor],i=this.random;for(let a=0;a<t;a++){let t=e.mirror&&a%2==1?-1:1,o=e.offset??[0,0,0],s=e.spread??0,c=[r.at[0]+o[0]*t+(i()-.5)*2*s,r.at[1]+o[1]+(i()-.5)*2*s,r.at[2]+o[2]+(i()-.5)*2*s],l=e.jitter??0,u=[e.velocity[0]*t+(i()-.5)*2*l,e.velocity[1]+(i()-.5)*l,e.velocity[2]+(i()-.5)*2*l];this.particles.push({pos:n.point(r.bone,c),vel:u,age:0,life:e.life[0]+(e.life[1]-e.life[0])*i(),size:e.size,rot:e.align?ee(e.glyph,u):t<0?Math.PI-(e.rotation??0):(e.rotation??0)+(e.spin?i():0),spec:e,color:P(e.color),seed:i()})}}pack(){this.count=this.particles.length,this.particles.forEach((e,t)=>{let n=e.age/e.life,r=1-(1-n)*(1-n),i=g(0,.12,n)*(1-g(.62,1,n)),a=t*4;this.a.set([e.pos[0],e.pos[1],e.pos[2],e.size[0]+(e.size[1]-e.size[0])*r],a),this.b.set([M[e.spec.glyph],i,e.rot,+!!e.spec.glow],a),this.c.set([e.color[0],e.color[1],e.color[2],e.seed],a)})}};function F(e){let t=parseInt(e.replace(`#`,``),16),n=e=>(e/255)**2.2;return[n(t>>16&255),n(t>>8&255),n(t&255)]}var I=e=>{let t=Number(e.toFixed(5)).toString();return t.includes(`.`)||t.includes(`e`)?t:`${t}.0`},L=e=>`vec2(${I(e[0])}, ${I(e[1])})`,R=e=>`vec3(${I(e[0])}, ${I(e[1])}, ${I(e[2])})`;function z(e){let t=l(i(),e[0],e[1],e[2]);return`mat3(${[0,1,2].map(e=>[t[e],t[4+e],t[8+e]]).flat().map(I).join(`, `)})`}function B(e){let t=[`vec2 map(vec3 p) {`,`  vec2 r = vec2(1e9, 0.0);`,`  vec3 l;`],n=new Set,r=e=>(n.has(e)||(n.add(e),t.push(`  vec3 b${e} = (uBones[${e}] * vec4(p, 1.0)).xyz;`)),`b${e}`);return e.spec.parts.forEach((n,i)=>{let a=r(e.boneIndex(n.bone,`parts[${i}]`)),o=n.at??[0,0,0],s=n.rot?`${z(n.rot)} * (${a} - ${R(o)})`:`${a} - ${R(o)}`;t.push(`  l = ${s};`);let c=I(e.materialId(n.material,`parts[${i}]`));if(n.shape===`hem`){t.push(`  r.x = smax(r.x, ${I(n.y)} + ${I(n.amplitude)} * sin(atan(l.z, l.x) * ${I(n.waves)} + uTime * ${I(n.speed)}) - l.y, ${I(n.blend)});`);return}let l=n.clip?`max(${H(n)}, dot(l, ${R(V(n.clip.normal))}) - ${I(n.clip.offset??0)})`:H(n),u=I(n.blend??0);t.push(n.op===`sub`?`  opSub(r, ${l}, ${u});`:`  opAdd(r, ${l}, ${c}, ${u});`)}),t.push(...U(e,r)),t.push(`  r.x *= uScaleFix;`,`  return r;`,`}`),t.join(`
`)}function V(e){let t=Math.hypot(...e)||1;return[e[0]/t,e[1]/t,e[2]/t]}function H(e){switch(e.shape){case`sphere`:return`sdSphere(l, ${I(e.radius)})`;case`ellipsoid`:return`sdEllipsoid(l, ${R(e.radii)})`;case`roundBox`:return`sdRoundBox(l, ${R(e.half)}, ${I(e.round)})`;case`capsule`:return`sdCapsule(l, ${R(e.from)}, ${R(e.to)}, ${I(e.radius)})`;case`roundCone`:return`sdRoundCone(l, ${R(e.from)}, ${R(e.to)}, ${I(e.r1)}, ${I(e.r2)})`;case`cylinder`:return`sdCylinder(l, ${I(e.radius)}, ${I(e.half)}, ${I(e.round)})`;case`frame`:return`sdFrame(l, ${L(e.half)}, ${I(e.corner)}, ${I(e.width)}, ${I(e.depth)})`;case`plate`:return`sdPlate(l, ${L(e.half)}, ${I(e.corner)}, ${I(e.depth)})`;case`hem`:throw Error(`unreachable`)}}function U(e,t){let n=e.spec.eyes;if(!n)return[];let r=t(e.boneIndex(n.bone,`eyes`)),i=[];if(n.kind===`ball`){let t=I(e.materialId(n.lid,`eyes.lid`)),a=n.radius;n.at.forEach((n,o)=>{let s=o===0?`-1.0`:`1.0`;i.push(`  l = ${r} - ${R(n)};`,`  opAdd(r, length(l) - ${I(a)}, ${I(e.eyeIds[o])}, 0.0);`,`  {`,`    float tilt = uFaceB.w * ${s};`,`    vec3 q = vec3(mat2(cos(tilt), sin(tilt), -sin(tilt), cos(tilt)) * l.xy, l.z);`,`    float shell = length(q) - ${I(a*1.1)};`,`    float lid = clamp(uFaceA.y + uFaceD.w * ${s} * 0.38 - uFaceD.z * 0.1, 0.0, 1.0);`,`    float top = mix(${I(a*1.18)}, ${I(-a*.14)}, max(uFaceA.x, lid));`,`    float bottom = mix(${I(-a*1.18)}, ${I(-a*.02)}, uFaceA.z * 0.85);`,`    opAdd(r, min(max(shell, top - q.y), max(shell, q.y - bottom)), ${t}, 0.0);`,`  }`)})}else{let t=I(e.materialId(n.material,`eyes.material`)),[a,o,s]=n.radii;i.push(`  float grow = 1.0 + 0.2 * uFaceD.z;`),n.at.forEach((e,n)=>{let c=n===0?`-1.0`:`1.0`;i.push(`  float open${n} = max(0.12, (1.0 - max(uFaceA.x, clamp(uFaceA.y + uFaceD.w * ${c} * 0.45, 0.0, 1.0))) * (1.0 - 0.6 * uFaceA.z));`,`  l = ${r} - ${R(e)} - vec3(uFaceB.y * ${I(a*.45)}, uFaceB.z * ${I(o*.3)}, 0.0);`,`  opAdd(r, sdEllipsoid(l, vec3(${I(a)} * grow, ${I(o)} * grow * open${n}, ${I(s)})), ${t}, 0.0);`)})}return i}var W=e=>R(F(e));function G(e,t){let n=e.glows?`uGlow * ${I(e.emitStrength??1)}`:e.emit?`${W(e.emit)} * ${I(e.emitStrength??1)}`:`vec3(0.0)`;return`Material(uAlbedo[${t}], ${I(e.f0??.04)}, ${I(e.spec??.5)}, ${I(e.shininess??40)}, ${I(e.metal??0)}, ${I(e.rim??.5)}, ${I(e.sheen??0)}, ${I(e.sss??0)}, ${e.sssColor?W(e.sssColor):`vec3(0.0)`}, ${n}, ${I(e.gloss??.3)})`}var K=e=>e.map(e=>`k == ${e}`).join(` || `);function ne(e){let t=[`Material getMaterial(float id, vec3 p, vec3 n) {`,`  int k = int(id + 0.5);`,`  Material m = material(vec3(0.5));`];return e.materials.forEach(({id:e,spec:n},r)=>t.push(`  ${r?`else `:``}if (k == ${e}) m = ${G(n,r)};`)),e.spec.paints?.forEach((n,r)=>{let i=e.boneIndex(n.bone,`paints[${r}]`),a=n.on.map(t=>e.materialId(t,`paints[${r}]`)),o=I(n.soft??.15),s=n.kind===`sphere`?`(length(q) - ${I(n.radius??.1)}) / ${I(n.radius??.1)}`:`q.z > 0.0 ? length(q.xy / ${L(n.radii??[.1,.1])}) - 1.0 : 1.0`;t.push(`  if (${K(a)}) {`,`    vec3 q = (uBones[${i}] * vec4(p, 1.0)).xyz - ${R(n.at)};`,`    float e = ${s};`,`    m.albedo = mix(m.albedo, ${W(n.color)}, (1.0 - smoothstep(-${o}, ${o}, e)) * ${I(n.opacity??1)});`,`  }`)}),t.push(...J(e),...Y(e),`  return m;`,`}`),t.join(`
`)}function re(e){let t=[`void surface(float id, vec3 p, inout vec3 n, inout Material m) {`,`  int k = int(id + 0.5);`];for(let{id:n,spec:r,name:i}of e.materials){let a=r.surface;if(!a)continue;let o=e.boneIndex(a.bone??`root`,`materials.${i}.surface`),s=I(a.strength??.5);t.push(`  if (k == ${n}) {`,`    vec3 q = (uBones[${o}] * vec4(p, 1.0)).xyz * ${I(a.scale)};`,`    float detail = ${s} * (1.0 - smoothstep(0.25, 0.9, gPixel * ${I(a.scale)}));`,...q(a.kind,a.color),`  }`)}return t.push(`}`),t.join(`
`)}function q(e,t){let n=e=>[`    vec3 g = vec3(noise3(${e}), noise3(${e} + 17.3), noise3(${e} + 41.7)) - 0.5;`,`    g -= n * dot(g, n);`];switch(e){case`fur`:return[...n(`q`),`    n = normalize(n + g * 0.5 * detail);`,`    float clump = noise3(q * 0.23);`,`    m.albedo *= mix(1.0, 0.9 + 0.2 * clump, detail);`];case`scales`:return[`    float c = noise3(q);`,`    float e = 0.12;`,`    vec3 grad = vec3(noise3(q + vec3(e, 0, 0)), noise3(q + vec3(0, e, 0)), noise3(q + vec3(0, 0, e))) - c;`,`    grad -= n * dot(grad, n);`,`    n = normalize(n - grad * 2.2 * detail);`,`    float seam = 1.0 - smoothstep(0.03, 0.13, abs(c - 0.5));`,`    m.albedo = mix(m.albedo, ${t?W(t):`m.albedo * 0.55`}, seam * 0.7 * detail);`,`    m.albedo *= 0.9 + 0.2 * noise3(q * 0.31) * detail;`];case`speckle`:return[`    float spot = smoothstep(0.66, 0.7, noise3(q)) * (0.6 + 0.4 * noise3(q * 0.37));`,`    m.albedo = mix(m.albedo, ${t?W(t):`m.albedo * 0.6`}, spot * detail);`];case`ripple`:return[...n(`q`),`    n = normalize(n + g * 0.35 * detail);`]}}function J(e){let t=e.spec.eyes;if(t?.kind!==`ball`)return[];let n=e.boneIndex(t.bone,`eyes`),r=[];return t.at.forEach((i,a)=>{r.push(`  if (k == ${e.eyeIds[a]}) {`,`    vec3 q = normalize((uBones[${n}] * vec4(p, 1.0)).xyz - ${R(i)});`,`    vec3 g = normalize(vec3(uFaceB.y * 0.5, uFaceB.z * 0.38, 1.0));`,`    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), g));`,`    vec3 up = cross(g, right);`,`    vec2 s = vec2(dot(q, right), dot(q, up));`,`    float front = step(0.0, dot(q, g));`,`    float aa = gPixel / ${I(t.radius)} + 0.02;`,`    float rr = length(s);`,`    float iris = front - front * smoothstep(${I(t.irisSize)} - aa, ${I(t.irisSize)} + aa, rr);`,`    float ps = ${I(t.pupilSize)} * (1.0 - 0.4 * uFaceD.z);`,`    float pupil = front - front * smoothstep(ps - aa, ps + aa, length(s / vec2(${I(t.pupilAspect??1)}, 1.0)));`,`    vec3 irisCol = ${W(t.iris)} * (0.55 + 0.9 * smoothstep(${I(t.irisSize)}, 0.0, rr)) * (0.7 + 0.3 * hash12(floor(vec2(atan(s.y, s.x) * 9.0, rr * 30.0))));`,`    vec3 albedo = mix(vec3(0.82, 0.8, 0.78), irisCol, iris);`,`    albedo = mix(albedo, vec3(0.004), pupil);`,`    m = Material(albedo, 0.06, 2.4, 600.0, 0.0, 0.15, 0.0, 0.0, vec3(0.0), vec3(0.0), 1.0);`,`  }`)}),r}function Y(e){let t=e.spec.face;if(!t)return[];if(t.kind===`screen`){let n=e.boneIndex(t.bone,`face`);return[`  if (k == ${e.materialId(t.material,`face.material`)}) {`,`    vec2 q = (uBones[${n}] * vec4(p, 1.0)).xy - ${L(t.center)};`,`    m.emit += screenLight(q, ${W(t.color)}, ${I(t.cell)}, ${L(t.half)}, ${I(t.corner)});`,`  }`]}let n=e.boneIndex(t.bone,`face`),r=t.on.map(t=>e.materialId(t,`face.on`)),i=t.width;return[`  if (${K(r)}) {`,`    vec3 q = (uBones[${n}] * vec4(p, 1.0)).xyz - ${R(t.at)};`,`    if (q.z > -0.02) {`,`      vec3 mo = mouth(q.xy, ${I(i)}, uFaceB.x * ${I(i*1.1)}, uFaceD.y, uFaceA.w, uFaceD.w, ${I(i*.12)}, gPixel * 0.8);`,`      float a = mo.x;`,`      vec3 inner = ${W(t.color)} * (1.25 - 0.5 * mo.z);`,`      m.albedo = mix(m.albedo, mix(inner, ${W(t.tongue)}, mo.y), a);`,`      m.spec *= 1.0 - 0.6 * a; m.sss *= 1.0 - a; m.sheen *= 1.0 - a; m.emit *= 1.0 - a;`,`    }`,`  }`]}var X=`
const vec3 KEY = vec3(-0.4485, 0.6997, 0.5562);
const vec3 FILL = vec3(0.8521, -0.1504, 0.5013);
const vec3 BACK = vec3(0.5529, 0.5529, -0.6233);

struct Material {
  vec3 albedo;
  float f0;
  float spec;
  float shininess;
  float metal;
  float rim;
  float sheen;
  float sss;
  vec3 sssColor;
  vec3 emit;
  float gloss;
};

Material material(vec3 albedo) {
  return Material(albedo, 0.04, 0.5, 40.0, 0.0, 0.5, 0.0, 0.0, vec3(0.0), vec3(0.0), 0.3);
}

/* the studio as seen in a reflection along r; gloss tightens the edges of the lights */
vec3 environment(vec3 r, float gloss) {
  float up = r.y;
  float horizon = 0.05 + 0.12 * smoothstep(-0.25, 0.3, up);
  float softbox = 1.1 * smoothstep(mix(0.42, 0.66, gloss), mix(0.78, 0.7, gloss), up) * smoothstep(-0.9, mix(-0.2, -0.75, gloss), r.z - 0.6 * abs(r.x));
  float window = 2.6 * smoothstep(mix(0.86, 0.95, gloss), mix(0.97, 0.965, gloss), dot(r, KEY));
  float strip = 0.5 * smoothstep(0.6, 0.85, -r.x) * smoothstep(-0.35, 0.05, up) * (1.0 - smoothstep(0.2, 0.5, up));
  float floorBounce = 0.06 * smoothstep(0.0, -0.6, up);
  return vec3(0.97, 0.99, 1.04) * (horizon + softbox + window + strip) + vec3(1.0, 0.92, 0.85) * floorBounce;
}

float softShadow(vec3 ro, vec3 rd, float tmin, float tmax, float k) {
  float res = 1.0;
  float t = tmin;
  for (int i = ZERO; i < 32; i++) {
    float h = map(ro + rd * t).x;
    res = min(res, k * h / t);
    t += clamp(h, 0.012, 0.2);
    if (res < 0.002 || t > tmax) break;
  }
  res = clamp(res, 0.0, 1.0);
  return res * res * (3.0 - 2.0 * res);
}

float ambientOcclusion(vec3 p, vec3 n) {
  float occ = 0.0, sca = 1.0;
  for (int i = ZERO; i < 5; i++) {
    float h = 0.012 + 0.12 * float(i) / 4.0;
    occ += (h - map(p + h * n).x) * sca;
    sca *= 0.85;
  }
  return clamp(1.0 - 2.2 * occ, 0.0, 1.0);
}

/* 0 where the body is thick behind the surface, 1 where light gets through */
float thinness(vec3 p, vec3 n) {
  float s = 0.0;
  for (int i = ZERO; i < 3; i++) {
    float h = 0.05 + 0.09 * float(i);
    s += clamp((map(p - n * h).x + h) / h, 0.0, 1.0);
  }
  return s / 3.0;
}

vec3 shade(Material m, vec3 p, vec3 n, vec3 v) {
  vec3 key = KEY;
  float sh = softShadow(p + n * 0.004, key, 0.01, 2.5, 9.0);
  float ao = ambientOcclusion(p, n);

  float ndl = dot(n, key);
  /* a little wrap so the terminator is soft, like a moulded part */
  float keyLight = max(0.0, (ndl + 0.12) / 1.12) * sh;
  float fill = max(0.0, dot(n, FILL));
  float sky = 0.5 + 0.5 * n.y;
  float ndv = max(0.0, dot(n, v));
  float fres = m.f0 + (1.0 - m.f0) * pow(1.0 - ndv, 5.0);
  vec3 r = reflect(-v, n);
  float specOcc = mix(ao, 1.0, 0.35) * mix(sh, 1.0, 0.6);
  vec3 env = environment(r, m.gloss) * fres * specOcc;
  float hi = m.spec * pow(max(0.0, dot(n, normalize(key + v))), m.shininess) * sh;
  float back = max(0.0, dot(n, BACK));
  float rim = m.rim * back * back * pow(1.0 - ndv, 1.6);
  float bounce = 0.1 * max(0.0, -n.y);

  float diffuse = (0.06 + 0.12 * sky) * ao + 1.2 * keyLight + 0.16 * fill * ao + bounce * ao;
  vec3 tint = vec3(1.0 - m.metal) + m.metal * m.albedo * 2.2;
  vec3 col = m.albedo * diffuse * (1.0 - fres * 0.6);
  col += (env + hi) * tint;
  col += rim * vec3(0.62, 0.78, 1.0) * (0.35 + m.albedo);
  /* velvet: fibres catch light at grazing angles */
  col += m.sheen * pow(1.0 - ndv, 2.5) * (0.4 + 0.6 * keyLight) * (m.albedo * 0.7 + 0.3);

  if (m.sss > 0.0) {
    float th = thinness(p, n);
    float through = pow(clamp(dot(v, -key) * 0.5 + 0.5, 0.0, 1.0), 2.0);
    col += m.sssColor * m.sss * (0.18 + 0.55 * th + 0.4 * through * th) * (0.55 + 0.45 * ao);
  }
  return col + m.emit;
}

vec3 aces(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
`,ie=`
vec3 calcNormal(vec3 p) {
  vec3 n = vec3(0.0);
  for (int i = ZERO; i < 4; i++) {
    vec3 e = 0.5773 * (2.0 * vec3(float(((i + 3) >> 1) & 1), float((i >> 1) & 1), float(i & 1)) - 1.0);
    n += e * map(p + 0.0006 * e).x;
  }
  return normalize(n);
}

vec4 over(vec4 top, vec4 under) { return top + under * (1.0 - top.a); }

void main() {
  vec2 uv = (2.0 * gl_FragCoord.xy - uResolution) / uResolution.y;
  float pitch = uCamera.w;
  vec3 target = vec3(0.0, uCamera.x, 0.0);
  vec3 ro = target + uCamera.y * vec3(0.0, sin(pitch), cos(pitch));
  vec3 fw = normalize(target - ro);
  vec3 rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0)));
  vec3 up = cross(rt, fw);
  vec3 rd = normalize(fw + (uv.x * rt + uv.y * up) * uCamera.z);
  float pixelAngle = 2.0 * uCamera.z / uResolution.y;

  vec4 body = vec4(0.0);
  float hitT = -1.0;
  vec3 oc = ro - uBound.xyz;
  float b = dot(oc, rd);
  float disc = b * b - dot(oc, oc) + uBound.w * uBound.w;
  if (disc > 0.0) {
    float s = sqrt(disc);
    float t = max(-b - s, 0.0);
    float tEnd = -b + s;
    float nearest = 1e9;
    float nearestT = 0.0;
    for (int i = ZERO; i < 140; i++) {
      float d = map(ro + rd * t).x;
      float px = t * pixelAngle;
      if (d < 0.2 * px) { hitT = t; break; }
      float ratio = d / px;
      if (ratio < nearest) { nearest = ratio; nearestT = t; }
      t += d * 0.85;
      if (t > tEnd) break;
    }
    float coverage = hitT > 0.0 ? 1.0 : 1.0 - smoothstep(0.2, 1.0, nearest);
    if (coverage > 0.0) {
      float tt = hitT > 0.0 ? hitT : nearestT;
      vec3 p = ro + rd * tt;
      gPixel = tt * pixelAngle;
      vec3 n = calcNormal(p);
      float id = map(p).y;
      Material m = getMaterial(id, p, n);
      surface(id, p, n, m);
      vec3 col = pow(aces(shade(m, p, n, -rd) * uExposure), vec3(1.0 / 2.2));
      body = vec4(col * coverage, coverage);
      if (hitT < 0.0) hitT = tt;
    }
  }

  vec4 floorLayer = vec4(0.0);
  if (uFloor > 0.0 && body.a < 1.0 && rd.y < 0.0) {
    vec3 fp = ro + rd * (-ro.y / rd.y);
    float r = length(fp.xz - uBound.xz);
    float reach = uBound.w * 1.15;
    if (r < reach) {
      float sky = softShadow(fp + vec3(0.0, 0.002, 0.0), vec3(0.1191, 0.9800, 0.1588), 0.02, 3.0, 3.2);
      float contact = 1.0 - smoothstep(0.0, 0.28, map(fp).x);
      float dark = (1.0 - sky) * 0.4 + contact * contact * 0.32;
      dark *= 1.0 - smoothstep(reach * 0.45, reach, r);
      /* a shadow fades as what casts it rises */
      dark *= mix(1.0, 0.5, smoothstep(0.0, 0.45, uLift));
      /* the state's light pooling on the floor */
      vec3 pool = uGlow * uGlowPool * exp(-r * r * 5.0) * (1.0 - dark);
      floorLayer = vec4(uShadow * dark + pool, dark) * uFloor;
    }
  }

  vec4 front = vec4(0.0);
  vec4 back = vec4(0.0);
  float pixel = 2.0 / uResolution.y;
  for (int i = 0; i < uFxCount; i++) {
    vec4 A = uFxA[i];
    vec4 B = uFxB[i];
    vec3 d = A.xyz - ro;
    float z = dot(d, fw);
    if (z < 0.1) continue;
    float scale = 1.0 / (z * uCamera.z);
    vec2 q = (uv - vec2(dot(d, rt), dot(d, up)) * scale) / (A.w * scale);
    if (dot(q, q) > 2.0) continue;
    float cr = cos(B.z), sr = sin(B.z);
    q = mat2(cr, -sr, sr, cr) * q;
    vec2 g = glyph(int(B.x + 0.5), q, pixel / (A.w * scale));
    float a = g.x * B.y;
    if (a < 0.002) continue;
    vec3 col = mix(uFxC[i].rgb, vec3(1.0), clamp(g.y, 0.0, 1.0)) * (1.0 + min(g.y, 0.0));
    vec4 layer = B.w > 0.5 ? vec4(col * a, 0.0) : vec4(col * a, a);
    if (hitT > 0.0 && hitT < length(d)) back = over(layer, back);
    else front = over(layer, front);
  }

  fragColor = over(front, over(body, over(back, floorLayer)));
}
`,ae=`
/* q: point in mouth space (x right, y up); w: half width; open: lip
   separation in the same units; round: 0 for "ah"/"ee", 1 for "oo";
   smile: -1..1; crooked: -1..1 tilts and wobbles the line, as when something
   is wrong; t: half the stroke; px: a pixel in mouth units.
   Returns coverage, tongue coverage, and depth inside the mouth (0 at the lips, 1 deep). */
vec3 mouth(vec2 q, float w, float open, float round, float smile, float crooked, float t, float px) {
  float opened = smoothstep(0.0, 0.25 * w, open);
  w *= 1.0 - 0.3 * round * opened;
  open *= 1.0 + 0.1 * round;
  /* an "oo" pushes the lips forward and flattens the smile out of them */
  float bend = smile * 0.55 * (1.0 - 0.7 * round * opened);

  float u = clamp(q.x / w, -1.0, 1.0);
  float bulge = sqrt(max(1.0 - u * u, 0.0));
  float line = bend * w * u * u + crooked * w * (0.22 * u + 0.12 * sin(u * 6.0));
  float upper = line + open * (0.22 + 0.45 * round) * bulge;
  float lower = line - open * bulge;

  /* vertical distances are cheap and exact along y; the slope converts the
     antialiasing width so the steep sides near the corners stay crisp */
  float steep = abs(u) / max(bulge, 0.08);
  float slope = abs(2.0 * bend * u) + abs(crooked) * 0.9 + open / w * steep;
  float aa = px * sqrt(1.0 + min(slope * slope, 36.0));

  /* the lips taper toward the corners once the mouth is open */
  float lip = t * mix(1.0, sqrt(bulge), opened);
  float inside = max(q.y - upper, lower - q.y);
  float body = abs(q.x) <= w ? inside - lip : 1e3;
  /* round caps finish the closed stroke; an open mouth's lips already meet in a point */
  float cap = length(vec2(abs(q.x) - w, q.y - bend * w - crooked * w * (0.22 * sign(q.x) + 0.12 * sin(6.0 * sign(q.x))))) - t;
  float a = max(1.0 - smoothstep(-aa, aa, body), (1.0 - smoothstep(-px, px, cap)) * (1.0 - opened));

  /* a tongue resting on the lower lip, only inside the opening */
  float hole = 1.0 - smoothstep(-aa, aa, inside);
  vec2 tq = vec2(q.x / (w * (0.5 - 0.1 * round)), (q.y + open * 0.78) / max(0.42 * open, 1e-4));
  float tongue = (1.0 - smoothstep(-0.08, 0.08, length(tq) - 1.0)) * hole * smoothstep(0.08, 0.35, open / w);

  float depth = clamp(-inside / max(0.5 * open, 1e-4), 0.0, 1.0) * hole;
  return vec3(a, tongue, depth);
}
`,oe=`
float fxSegment(vec2 p, vec2 a, vec2 b) {
  vec2 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h);
}

float fxDot2(vec2 v) { return dot(v, v); }

float fxHeart(vec2 p) {
  p.x = abs(p.x);
  if (p.y + p.x > 1.0) return sqrt(fxDot2(p - vec2(0.25, 0.75))) - sqrt(2.0) / 4.0;
  return sqrt(min(fxDot2(p - vec2(0.0, 1.0)), fxDot2(p - 0.5 * max(p.x + p.y, 0.0)))) * sign(p.x - p.y);
}

float fxTeardrop(vec2 p, float r1, float r2, float h) {
  p.x = abs(p.x);
  float b = (r1 - r2) / h;
  float a = sqrt(1.0 - b * b);
  float k = dot(p, vec2(-b, a));
  if (k < 0.0) return length(p) - r1;
  if (k > a * h) return length(p - vec2(0.0, h)) - r2;
  return dot(p, vec2(a, b)) - r1;
}

float fxStar(vec2 p, float r, float rf) {
  const vec2 k1 = vec2(0.809016994375, -0.587785252292);
  const vec2 k2 = vec2(-k1.x, k1.y);
  p.x = abs(p.x);
  p -= 2.0 * max(dot(k1, p), 0.0) * k1;
  p -= 2.0 * max(dot(k2, p), 0.0) * k2;
  p.x = abs(p.x);
  p.y -= r;
  vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
  float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
  return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}

float fxTriangle(vec2 p, float r) {
  const float k = 1.7320508;
  p.x = abs(p.x) - r;
  p.y = p.y + r / k;
  if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
  p.x -= clamp(p.x, -2.0 * r, 0.0);
  return -length(p) * sign(p.y);
}

/* an exclamation mark, tapering toward its dot */
float fxExclaim(vec2 p) {
  float bar = fxSegment(p, vec2(0.0, -0.2), vec2(0.0, 0.8)) - mix(0.11, 0.19, clamp((p.y + 0.2), 0.0, 1.0));
  return min(bar, length(p - vec2(0.0, -0.66)) - 0.15);
}

/* coverage, highlight */
vec2 glyph(int g, vec2 p, float px) {
  float d = 1e9;
  float light = 0.0;
  float soft = 0.0;
  if (g == 0) {
    d = min(min(fxSegment(p, vec2(-0.6, 0.6), vec2(0.6, 0.6)), fxSegment(p, vec2(0.6, 0.6), vec2(-0.6, -0.6))), fxSegment(p, vec2(-0.6, -0.6), vec2(0.6, -0.6))) - 0.16;
  } else if (g == 1) {
    float ring = abs(length(p) - 0.82) - 0.07;
    float shine = length(p - vec2(-0.32, 0.36)) - 0.17;
    d = min(ring, shine);
    light = 1.0 - smoothstep(-px, px, shine);
    soft = 0.14 * (1.0 - smoothstep(0.75, 0.82, length(p)));
  } else if (g == 2) {
    vec2 q = abs(p);
    d = (sqrt(q.x) + sqrt(q.y) - 0.92) * 0.45;
    light = 1.0 - smoothstep(0.0, 0.35, length(p));
  } else if (g == 3) {
    d = fxHeart(p * 0.56 + vec2(0.0, 0.5)) / 0.56;
    light = (1.0 - smoothstep(-px, px, length(p - vec2(-0.38, 0.38)) - 0.13)) * 0.8;
  } else if (g == 4) {
    vec2 h = p - vec2(-0.28, -0.55);
    float head = (length(mat2(0.92, 0.39, -0.39, 0.92) * h / vec2(0.32, 0.23)) - 1.0) * 0.23;
    float stem = fxSegment(p, vec2(0.02, -0.5), vec2(0.02, 0.78)) - 0.07;
    float flag = fxSegment(p, vec2(0.02, 0.78), vec2(0.42, 0.36)) - 0.09;
    d = min(head, min(stem, flag));
  } else if (g == 5) {
    vec2 c = p - vec2(-1.1, 0.0);
    float a = atan(c.y, c.x);
    d = max(abs(length(c) - 1.45) - 0.1, (abs(a) - 0.48) * 1.45);
  } else if (g == 6) {
    float r = length(p);
    return vec2((1.0 - smoothstep(0.15, 1.0, r)) * 0.75, 0.25 + 0.35 * p.y);
  } else if (g == 7) {
    d = abs(length(p) - 0.84) - 0.06;
  } else if (g == 8) {
    d = fxTeardrop(p + vec2(0.0, 0.35), 0.55, 0.06, 1.05);
    light = (1.0 - smoothstep(-px, px, length(p - vec2(-0.2, -0.2)) - 0.12)) * 0.9;
  } else if (g == 9) {
    d = fxSegment(p, vec2(-1.0, 0.0), vec2(1.0, 0.0)) - 0.12 * (1.0 - abs(p.x) * 0.7);
    light = 0.6;
  } else if (g == 10) {
    float r = length(p);
    return vec2(exp(-r * r * 5.0), 1.0 - smoothstep(0.0, 0.3, r));
  } else if (g == 11) {
    d = (length(p / vec2(0.3, 0.95)) - 1.0) * 0.3;
    light = -0.35 * (1.0 - smoothstep(0.0, 0.05 + px, abs(p.x + 0.04 * p.y)));
  } else if (g == 13) {
    d = fxExclaim(p);
    light = 0.3 * (1.0 - smoothstep(-px, px, fxSegment(p, vec2(-0.05, 0.1), vec2(-0.05, 0.7)) - 0.035));
  } else if (g == 14) {
    d = fxTriangle(p - vec2(0.0, -0.12), 0.82) - 0.14;
    /* a white mark on the coloured sign */
    light = 1.0 - smoothstep(-px, px, fxExclaim((p - vec2(0.0, -0.08)) / 0.52) * 0.52);
  } else if (g == 15) {
    vec2 q = abs(p) - vec2(0.32, 0.78);
    d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 0.06;
    light = 0.35 * step(0.0, p.x);
  } else if (g == 16) {
    float c = min(min(length(p - vec2(-0.48, -0.08)) - 0.4, length(p - vec2(0.08, 0.18)) - 0.55), length(p - vec2(0.56, -0.1)) - 0.36);
    d = max(c, -p.y - 0.44);
    light = 0.45 * smoothstep(-0.2, 0.7, p.y) - 0.25 * (1.0 - smoothstep(-0.45, -0.1, p.y));
  } else if (g == 17) {
    d = fxStar(p, 0.92, 0.46) - 0.06;
    light = 0.5 * (1.0 - smoothstep(0.0, 0.45, length(p - vec2(-0.12, 0.18))));
  } else if (g == 18) {
    float r = length(p);
    float teeth = 0.66 + 0.2 * smoothstep(-0.25, 0.25, cos(atan(p.y, p.x) * 8.0));
    d = max(r - teeth, 0.26 - r);
    light = 0.3 * (1.0 - smoothstep(0.3, 0.7, length(p - vec2(-0.2, 0.25))));
  } else {
    d = length(p) - 0.9;
    light = 0.35 * (1.0 - smoothstep(0.0, 0.6, length(p - vec2(-0.3, 0.35))));
  }
  return vec2(max(1.0 - smoothstep(-px, px, d), soft), light);
}
`,se=`
float sdSphere(vec3 p, float r) { return length(p) - r; }

float sdEllipsoid(vec3 p, vec3 r) {
  float k0 = length(p / r);
  float k1 = length(p / (r * r));
  return k0 * (k0 - 1.0) / max(k1, 1e-6);
}

float sdRoundBox(vec3 p, vec3 b, float r) {
  vec3 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
  vec3 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}

float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
  vec3 ba = b - a;
  float l2 = dot(ba, ba);
  float rr = r1 - r2;
  float a2 = l2 - rr * rr;
  float il2 = 1.0 / l2;
  vec3 pa = p - a;
  float y = dot(pa, ba);
  float z = y - l2;
  vec3 xv = pa * l2 - ba * y;
  float x2 = dot(xv, xv);
  float y2 = y * y * l2;
  float z2 = z * z * l2;
  float k = sign(rr) * rr * rr * x2;
  if (sign(z) * a2 * z2 > k) return sqrt(x2 + z2) * il2 - r2;
  if (sign(y) * a2 * y2 < k) return sqrt(x2 + y2) * il2 - r1;
  return (sqrt(x2 * a2 * il2) + y * rr) * il2 - r1;
}

/* along y, with rounded rims */
float sdCylinder(vec3 p, float r, float h, float rr) {
  vec2 d = vec2(length(p.xz) - r + rr, abs(p.y) - h + rr);
  return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - rr;
}

float sdRoundRect(vec2 p, vec2 b, float r) {
  vec2 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

/* a rounded-rectangle ring in the xy plane, extruded along z: gaskets, bezels */
float sdFrame(vec3 p, vec2 b, float corner, float w, float depth) {
  float ring = abs(sdRoundRect(p.xy, b, corner)) - w;
  vec2 e = vec2(ring, abs(p.z) - depth);
  return min(max(e.x, e.y), 0.0) + length(max(e, 0.0));
}

float sdPlate(vec3 p, vec2 b, float corner, float depth) {
  vec2 e = vec2(sdRoundRect(p.xy, b, corner), abs(p.z) - depth);
  return min(max(e.x, e.y), 0.0) + length(max(e, 0.0));
}

float smin(float a, float b, float k) {
  float h = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - h * h * k * 0.25;
}

float smax(float a, float b, float k) { return -smin(-a, -b, k); }

/* union that keeps the material of whichever surface is nearer */
void opAdd(inout vec2 r, float d, float id, float k) {
  float m = d < r.x ? id : r.y;
  r.x = k > 0.0 ? smin(r.x, d, k) : min(r.x, d);
  r.y = m;
}

void opSub(inout vec2 r, float d, float k) {
  r.x = k > 0.0 ? smax(r.x, -d, k) : max(r.x, -d);
}

float hash13(vec3 p3) {
  p3 = fract(p3 * 0.1031);
  p3 += dot(p3, p3.zyx + 31.32);
  return fract((p3.x + p3.y) * p3.z);
}

/* smooth value noise, 0–1 */
float noise3(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y),
    mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y),
    f.z);
}

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
`,ce=`
float sdBox2(vec2 p, vec2 b) {
  vec2 d = abs(p) - b;
  return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

float fxStarLed(vec2 p, float r, float rf) {
  const vec2 k1 = vec2(0.809016994375, -0.587785252292);
  const vec2 k2 = vec2(-k1.x, k1.y);
  p.x = abs(p.x);
  p -= 2.0 * max(dot(k1, p), 0.0) * k1;
  p -= 2.0 * max(dot(k2, p), 0.0) * k2;
  p.x = abs(p.x);
  p.y -= r;
  vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
  float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
  return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}

float sdSegment(vec2 p, vec2 a, vec2 b) {
  vec2 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h);
}

/* how lit a shape is at distance d: 1 inside, falling off over soft */
float lit(float d, float soft) { return 1.0 - smoothstep(-0.35, soft, d); }

float faceEyes(vec2 c, float soft) {
  vec2 g = vec2(uFaceB.y * 2.2, uFaceB.z * 1.4);
  float blink = uFaceA.x;
  float v = 0.0;
  for (int i = 0; i < 2; i++) {
    float side = i == 0 ? -1.0 : 1.0;
    float lid = clamp(uFaceA.y + uFaceD.w * side * 0.4, 0.0, 1.0);
    float closeTop = max(blink * 0.48, lid * 0.42);
    float closeBottom = max(blink * 0.48, uFaceA.z * 0.4);
    float cx = side * 4.5 + g.x;
    float top = 3.5 + 0.8 * uFaceD.z + g.y - 4.0 * closeTop;
    float bottom = -0.5 - 0.5 * uFaceD.z + g.y + 4.0 * closeBottom;
    float h = max((top - bottom) * 0.5, 0.32);
    float d = sdBox2(c - vec2(cx, (top + bottom) * 0.5), vec2(1.5 + 0.3 * uFaceD.z, h)) - 0.15;
    v = max(v, lit(d, soft));
  }
  return v;
}

/* a mouth of two lips, like the painted ones: open is in LED rows */
float faceMouth(vec2 c, float open, float round, float smile, float soft) {
  float opened = smoothstep(0.0, 0.8, open);
  float w = 3.4 - 1.4 * round * opened;
  vec2 m = c - vec2(0.0, -3.7 + 0.25 * open);
  float u = clamp(m.x / w, -1.0, 1.0);
  float bulge = sqrt(max(1.0 - u * u, 0.0));
  float line = smile * 0.9 * u * u;
  float inside = max(m.y - line - open * (0.2 + 0.45 * round) * bulge, line - open * bulge - m.y);
  float body = abs(m.x) <= w ? inside : 1e3;
  float rim = min(abs(body), length(vec2(abs(m.x) - w, m.y - smile * 0.9))) - 0.42;
  return max(lit(rim, soft), lit(body, soft) * 0.12 * opened);
}

float faceZ(vec2 c, vec2 at, float s, float soft) {
  vec2 p = (c - at) / s;
  float d = min(min(sdSegment(p, vec2(-1, 1), vec2(1, 1)), sdSegment(p, vec2(1, 1), vec2(-1, -1))), sdSegment(p, vec2(-1, -1), vec2(1, -1)));
  return lit(d * s - 0.32, soft);
}

bool is(float state, float id) { return abs(state - id) < 0.5; }

float faceFor(float state, vec2 c, float t, float soft) {
  float v = 0.0;
  if (is(state, E_THINKING)) {
    /* heavy-lidded eyes looking up, three dots pulsing in turn */
    v = faceEyes(c, soft);
    for (int i = 0; i < 3; i++) {
      float fi = float(i);
      float pulse = 0.5 + 0.5 * sin(t * 4.2 - fi * 1.1);
      float d = length(c - vec2(-2.4 + fi * 2.4, -4.4)) - 0.62;
      v = max(v, lit(d, soft) * (0.25 + 0.75 * pulse * pulse));
    }
  } else if (is(state, E_LISTENING)) {
    /* alert eyes over a live equaliser */
    v = faceEyes(c, soft);
    for (int i = 0; i < 7; i++) {
      float fi = float(i);
      float level = abs(sin(t * (5.0 + fi * 1.3) + fi * 1.7)) * (0.55 + 0.45 * sin(t * 2.3 + fi));
      float d = sdBox2(c - vec2(-4.5 + fi * 1.5, -4.6), vec2(0.42, 0.45 + 1.6 * level));
      v = max(v, lit(d, soft) * 0.9);
    }
  } else if (is(state, E_SPEAKING)) {
    /* the same two-lip mouth as the painted faces; closed, the lips meet in one bar */
    v = max(faceEyes(c, soft), faceMouth(c, uFaceB.x * 3.4, uFaceD.y, 0.0, soft));
  } else if (is(state, E_SLEEPING)) {
    /* closed eyes and rising z's */
    for (int i = 0; i < 2; i++) {
      float cx = i == 0 ? -4.5 : 4.5;
      float d = min(sdSegment(c, vec2(cx - 1.6, 1.4), vec2(cx, 0.6)), sdSegment(c, vec2(cx, 0.6), vec2(cx + 1.6, 1.4))) - 0.38;
      v = max(v, lit(d, soft));
    }
    for (int i = 0; i < 3; i++) {
      float k = fract(t * 0.22 + float(i) / 3.0);
      float fade = smoothstep(0.0, 0.15, k) * (1.0 - smoothstep(0.7, 1.0, k));
      v = max(v, faceZ(c, vec2(7.6 + k * 3.2, 1.2 + k * 5.0), 0.5 + k * 0.55, soft) * fade);
    }
  } else if (is(state, E_WORKING)) {
    /* narrowed eyes over a progress bar that fills, empties and fills again */
    v = faceEyes(c, soft);
    float rim = abs(sdBox2(c - vec2(0.0, -4.6), vec2(4.6, 0.95))) - 0.3;
    float fill = fract(t * 0.3) * 8.4;
    float bar = sdBox2(c - vec2(-4.2 + fill * 0.5, -4.6), vec2(fill * 0.5, 0.35));
    v = max(v, max(lit(rim, soft) * 0.55, lit(bar, soft)));
  } else if (is(state, E_ERROR)) {
    /* X eyes and a zigzag mouth */
    for (int i = 0; i < 2; i++) {
      vec2 e = c - vec2(i == 0 ? -4.5 : 4.5, 1.5);
      float d = min(sdSegment(e, vec2(-1.5, -1.5), vec2(1.5, 1.5)), sdSegment(e, vec2(-1.5, 1.5), vec2(1.5, -1.5))) - 0.42;
      v = max(v, lit(d, soft));
    }
    float zig = 1e3;
    for (int i = 0; i < 4; i++) {
      float x0 = -3.6 + float(i) * 1.8;
      zig = min(zig, sdSegment(c, vec2(x0, -4.6 + (i % 2 == 0 ? 0.6 : -0.6)), vec2(x0 + 1.8, -4.6 + (i % 2 == 0 ? -0.6 : 0.6))));
    }
    v = max(v, lit(zig - 0.4, soft));
  } else if (is(state, E_SURPRISED)) {
    /* round eyes with pinned pupils, and a little "o" */
    for (int i = 0; i < 2; i++) {
      vec2 e = c - vec2(i == 0 ? -4.5 : 4.5, 1.4);
      float ring = abs(length(e) - 2.0) - 0.42;
      v = max(v, max(lit(ring, soft), lit(length(e) - 0.62, soft)));
    }
    v = max(v, lit(abs(length(c - vec2(0.0, -4.7)) - 1.05) - 0.4, soft));
  } else if (is(state, E_CELEBRATING)) {
    /* star eyes that throb, and a wide open grin */
    float throb = 1.0 + 0.12 * sin(t * 9.0);
    for (int i = 0; i < 2; i++) {
      vec2 e = (c - vec2(i == 0 ? -4.5 : 4.5, 1.6)) / throb;
      v = max(v, lit(fxStarLed(e, 2.2, 0.48) * throb - 0.1, soft));
    }
    v = max(v, faceMouth(c - vec2(0.0, 0.6), 2.6, 0.0, 0.7, soft));
  } else if (is(state, E_SAD)) {
    /* eyes cut away at the outer top, a frown, and a tear now and then */
    for (int i = 0; i < 2; i++) {
      float side = i == 0 ? -1.0 : 1.0;
      float cx = side * 4.5;
      float box = sdBox2(c - vec2(cx, 1.0), vec2(1.5, 1.6)) - 0.15;
      float slope = (c.y - 1.9) + 0.55 * (c.x - cx) * side;
      v = max(v, lit(max(box, slope), soft));
    }
    float frown = max(abs(length(c - vec2(0.0, -7.2)) - 2.6) - 0.4, -(c.y + 5.4));
    v = max(v, lit(frown, soft));
    float k = fract(t * 0.35);
    float tear = length((c - vec2(-5.4, -0.6 - k * 5.0)) / vec2(0.8, 1.0)) - 0.6;
    v = max(v, lit(tear, soft) * smoothstep(0.0, 0.1, k) * (1.0 - smoothstep(0.6, 0.9, k)));
  } else if (is(state, E_HAPPY)) {
    /* ^ ^ and a smile */
    for (int i = 0; i < 2; i++) {
      float cx = i == 0 ? -4.5 : 4.5;
      float d = min(sdSegment(c, vec2(cx - 1.7, 0.4), vec2(cx, 2.2)), sdSegment(c, vec2(cx, 2.2), vec2(cx + 1.7, 0.4))) - 0.5;
      v = max(v, lit(d, soft));
    }
    float d = min(min(sdSegment(c, vec2(-3.0, -3.0), vec2(-1.3, -4.6)), sdSegment(c, vec2(-1.3, -4.6), vec2(1.3, -4.6))), sdSegment(c, vec2(1.3, -4.6), vec2(3.0, -3.0))) - 0.45;
    v = max(v, lit(d, soft));
  } else {
    v = faceEyes(c, soft);
  }
  return v;
}

/* the face at c, cross-faded from the previous state and glitched on a switch */
float face(vec2 c, float soft) {
  float row = floor(c.y);
  float tick = floor(uTime * 24.0);
  /* an error keeps glitching now and then */
  float glitch = max(uFaceC.w, is(uFaceC.x, E_ERROR) ? 0.6 * step(0.86, hash12(vec2(floor(uTime * 8.0), 7.7))) : 0.0);
  c.x += (hash12(vec2(row, tick)) - 0.5) * 7.0 * glitch * step(0.6, hash12(vec2(row * 1.7, tick)));
  float now = faceFor(uFaceC.x, c, uFaceD.x, soft);
  float before = faceFor(uFaceC.y, c, uFaceD.x, soft);
  float v = mix(before, now, uFaceC.z);
  return v * (1.0 - glitch * 0.45 * hash12(vec2(tick, 3.1)));
}

/* the emitted light of the matrix at a point on the screen (screen-local, in units) */
vec3 screenLight(vec2 q, vec3 color, float cell, vec2 extent, float corner) {
  vec2 c = q / cell;
  vec2 cellCentre = floor(c) + 0.5;
  vec2 f = fract(c) - 0.5;
  /* round LEDs, averaged out when one is smaller than a couple of pixels */
  float dotMask = 1.0 - smoothstep(0.26, 0.4, length(f));
  float footprint = gPixel / cell;
  dotMask = mix(dotMask, 0.5, smoothstep(0.18, 0.45, footprint));
  float led = face(cellCentre, 0.25);
  float glow = face(c, 1.6);
  float edge = smoothstep(0.0, 0.05, -sdRoundRect(q, extent, corner));
  /* a faint glare across the glass */
  float glare = 0.025 * smoothstep(0.1, 0.0, abs(q.x * 0.7 + q.y - extent.y * 0.35));
  vec3 lit = color * (led * dotMask * 2.1 + glow * 0.2) + glare + vec3(0.012, 0.016, 0.03) * dotMask;
  return lit * edge;
}
`,le=class extends Error{constructor(e,t){super(`${e}: ${t}`),this.name=`SpecError`}};function ue(e){let t=t=>{throw new le(e.id,t)},n=[{name:`root`,pivot:[0,0,0],index:0,parentIndex:-1}],r=new Map([[`root`,0]]);e.bones.forEach((e,i)=>{r.has(e.name)&&t(`bone "${e.name}" is declared twice`);let a=e.parent??`root`,o=r.get(a);o===void 0&&t(`bone "${e.name}" names parent "${a}", which is not declared before it`),r.set(e.name,i+1),n.push({...e,index:i+1,parentIndex:o})});let i=Object.entries(e.materials).map(([e,t],n)=>({name:e,id:n+1,spec:t})),a=new Map(i.map(e=>[e.name,e.id])),o=[i.length+1,i.length+2],s=(e,n)=>r.get(e)??t(`${n} names bone "${e}", which does not exist`),c=(e,n)=>a.get(e)??t(`${n} names material "${e}", which does not exist`);i.forEach(e=>{e.spec.shadeOf!==void 0&&c(e.spec.shadeOf,`materials.${e.name}.shadeOf`)}),e.parts.forEach((e,t)=>{s(e.bone,`parts[${t}]`),c(e.material,`parts[${t}]`)}),e.paints?.forEach((e,t)=>{s(e.bone,`paints[${t}]`),e.on.forEach(e=>c(e,`paints[${t}]`))});let l=n.map(()=>[]);for(let[t,n]of Object.entries(e.acting??{}))for(let[e,r]of Object.entries(n)){let n=s(e,`acting.${t}`);for(let[e,i]of Object.entries(r))l[n].push([t,e,i])}let u={};for(let[t,n]of Object.entries(e.anchors??{}))u[t]={bone:s(n.bone,`anchors.${t}`),at:n.at};for(let[n,r]of Object.entries(e.fx??{}))n!==`replace`&&r.forEach((e,r)=>{u[e.anchor]||t(`fx.${n}[${r}] names anchor "${e.anchor}", which does not exist`)});return{spec:e,bones:n,boneIndex:s,materials:i,materialId:c,eyeIds:o,acting:l,anchors:u}}var de={uResolution:`vec2`,uTime:`float`,uCamera:`vec4`,uBound:`vec4`,uBones:`mat4[]`,uScaleFix:`float`,uFaceA:`vec4`,uFaceB:`vec4`,uFaceC:`vec4`,uFaceD:`vec4`,uGlow:`vec3`,uShadow:`vec3`,uFloor:`float`,uLift:`float`,uGlowPool:`float`,uExposure:`float`,uAlbedo:`vec3[materials]`,uFxA:`vec4[fx]`,uFxB:`vec4[fx]`,uFxC:`vec4[fx]`,uFxCount:`int`};function fe(e,t){return Object.entries(de).map(([n,r])=>r===`mat4[]`?`uniform mat4 ${n}[${e}];`:r===`vec3[materials]`?`uniform vec3 ${n}[${Math.max(1,t)}];`:r===`vec4[fx]`?`uniform vec4 ${n}[${j}];`:`uniform ${r} ${n};`).join(`
`)}var pe=`#version 300 es
void main() {
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`,me=()=>w.map(e=>`#define E_${e.toUpperCase()} ${I(T[e])}`).join(`
`)+`
`;function he(e){let t=ue(e),n=[`#version 300 es`,`precision highp float;`,`precision highp int;`,fe(t.bones.length,t.materials.length),`out vec4 fragColor;`,`float gPixel = 0.001;`,`#define ZERO (min(int(uTime), 0))`,se,B(t),X,e.face?.kind===`screen`?me()+ce:``,e.face?.kind===`mouth`?ae:``,ne(t),re(t),oe,ie].join(`
`);return{spec:e,bones:t.bones,acting:t.acting,anchors:t.anchors,fragment:n,materials:t.materials.map(e=>e.name),albedo:new Float32Array(t.materials.flatMap(e=>F(e.spec.color))),stats:{parts:e.parts.length+(e.eyes?2:0),bones:t.bones.length,materials:t.materials.length,shaderLines:n.split(`
`).length}}}var ge=(e,t)=>[e[0]+t[0],e[1]+t[1],e[2]+t[2]],_e=(e,t)=>[e[0]-t[0],e[1]-t[1],e[2]-t[2]],ve=(e,t)=>[e[0]*t,e[1]*t,e[2]*t],ye=(e,t)=>e[0]*t[0]+e[1]*t[1]+e[2]*t[2],be=(e,t)=>[e[1]*t[2]-e[2]*t[1],e[2]*t[0]-e[0]*t[2],e[0]*t[1]-e[1]*t[0]],xe=e=>Math.hypot(e[0],e[1],e[2]);function Z(e){let t=xe(e)||1;return[e[0]/t,e[1]/t,e[2]/t]}var Se=[`rx`,`ry`,`rz`];function Ce(e,t){if(typeof e==`number`)return e;let[n,r=0,i=0,a=0]=e;return n+r*Math.sin(t*i*Math.PI*2+a)}var we=class{constructor(e,t=e.map(()=>[])){this.bones=e,this.acting=t,this.world=e.map(()=>i()),this.inverse=new Float32Array(e.length*16),this.tips=e.map(()=>null),this.spun=e.map(()=>({rx:0,ry:0,rz:0}))}bones;acting;world;inverse;tips;spun;scratch={t:i(),r:i(),j:i(),inv:i()};point(e,t){return f(this.world[e],t)}update(e,t,n,r,i){let{t:a,r:c,j:u,inv:f}=this.scratch;this.world[0].set(e);for(let e=1;e<this.bones.length;e++){let d=this.bones[e],p={rx:d.rest?.rx??0,ry:d.rest?.ry??0,rz:d.rest?.rz??0};for(let e of Se){for(let[n,r]of d.drive?.[e]??[])p[e]+=t[n]*r;let n=d.wave?.[e];n&&(p[e]+=n[0]*t.energy*Math.sin(r*n[1]*Math.PI*2+n[2]))}for(let[t,a,o]of this.acting[e]){let s=n[t];s<.001&&!(Array.isArray(o)&&o[4])||(p[a]+=s*Ce(o,r),Array.isArray(o)&&o[4]&&(this.spun[e][a]+=s*o[4]*i))}for(let t of Se)p[t]+=this.spun[e][t];let m=this.world[e];o(m,this.world[d.parentIndex],s(a,...d.pivot)),o(m,m,l(c,p.rx,p.ry,p.rz)),d.jiggle&&o(m,m,this.jiggle(e,m,i,u,f))}for(let e=0;e<this.bones.length;e++)this.inverse.set(d(f,this.world[e]),e*16)}jiggle(e,t,n,r,i){let{axis:a,length:o,freq:s,damping:c,maxAngle:l=.9}=this.bones[e].jiggle,h=f(t,[0,0,0]),g=ge(h,ve(Z(p(t,a)),o)),_=this.tips[e];if((!_||!(n>0))&&(_=this.tips[e]=_??{x:g,v:[0,0,0]},!(n>0)))return u(r,[0,1,0],0);let v=s*Math.PI*2;for(let e=0;e<3;e++)_.v[e]+=(v*v*(g[e]-_.x[e])-2*c*v*_.v[e])*n,_.x[e]+=_.v[e]*n;_.x=ge(h,ve(Z(_e(_.x,h)),o)),d(i,t);let y=Z(p(i,_e(_.x,h))),b=Z(a),x=be(b,y),S=xe(x);if(S<1e-6)return u(r,[0,1,0],0);let C=m(Math.atan2(S,ye(b,y)),0,l);return u(r,ve(x,1/S),C)}},Te=48,Q=128,Ee=null,De=class e{static shared(){return Ee??=new e}canvas=document.createElement(`canvas`);gl;programs=new Map;parallel;lastSyncBuild=-1/0;constructor(){let e=this.canvas.getContext(`webgl2`,{alpha:!0,premultipliedAlpha:!0,antialias:!1,depth:!1,stencil:!1,powerPreference:`high-performance`});if(!e)throw Error(`WebGL2 is not available`);this.gl=e,this.parallel=e.getExtension(`KHR_parallel_shader_compile`),e.enable(e.SCISSOR_TEST),e.clearColor(0,0,0,0),this.canvas.addEventListener(`webglcontextlost`,e=>e.preventDefault()),this.canvas.addEventListener(`webglcontextrestored`,()=>{this.programs.clear(),e.enable(e.SCISSOR_TEST),e.clearColor(0,0,0,0)})}program(e){let t=this.programs.get(e);if(t===`failed`)return null;if(t&&`program`in t)return t;if(!t){if(!this.parallel){let e=performance.now();if(e-this.lastSyncBuild<Te)return null;this.lastSyncBuild=e}let t=this.start(e);return this.programs.set(e,t),this.parallel?null:this.finish(e,t)}return this.parallel&&!this.gl.getProgramParameter(t.building,this.parallel.COMPLETION_STATUS_KHR)?null:this.finish(e,t)}reserve(e,t){let n=Math.ceil(e/Q)*Q,r=Math.ceil(t/Q)*Q;n>this.canvas.width&&(this.canvas.width=n),r>this.canvas.height&&(this.canvas.height=r)}start(e){let{gl:t}=this,n=(e,n)=>{let r=t.createShader(e);return t.shaderSource(r,n),t.compileShader(r),r},r=n(t.VERTEX_SHADER,pe),i=n(t.FRAGMENT_SHADER,e.fragment),a=t.createProgram();return t.attachShader(a,r),t.attachShader(a,i),t.linkProgram(a),{building:a,vertex:r,fragment:i}}finish(e,{building:t,vertex:n,fragment:r}){let{gl:i}=this;if(!i.getProgramParameter(t,i.LINK_STATUS)){let n=i.getShaderInfoLog(r)||i.getProgramInfoLog(t);throw this.programs.set(e,`failed`),Error(`${e.spec.id}: shader failed to build
${n}`)}i.deleteShader(n),i.deleteShader(r);let a={program:t,uniforms:Object.fromEntries(Object.keys(de).map(e=>[e,i.getUniformLocation(t,de[e].includes(`[`)?`${e}[0]`:e)])),character:e};return this.programs.set(e,a),a}},Oe=.2,ke=.1,Ae=class{constructor(e){this.canvas=e;let t=e.getContext(`2d`);if(!t)throw Error(`Canvas 2D is not available`);this.target=t}canvas;gpu=De.shared();target;character=null;load(e){this.character=e,this.gpu.program(e)}render(e){let t=this.character&&this.gpu.program(this.character);if(!t)return!1;let{gpu:n}=this,{gl:r}=n,{width:i,height:a}=e;(this.canvas.width!==i||this.canvas.height!==a)&&(this.canvas.width=i,this.canvas.height=a),n.reserve(i,a),r.viewport(0,0,i,a),r.scissor(0,0,i,a),r.clear(r.COLOR_BUFFER_BIT),r.useProgram(t.program);let o=t.uniforms,{spec:s}=t.character,c=e.pose,l=c.lift;return r.uniform2f(o.uResolution,e.width,e.height),r.uniform1f(o.uTime,e.time),r.uniform4f(o.uCamera,s.frame.target,s.frame.radius*e.framing/Oe,Oe,ke),r.uniform4f(o.uBound,0,s.bound.y+l,0,s.bound.radius),r.uniformMatrix4fv(o.uBones,!1,e.bones),r.uniform1f(o.uScaleFix,c.minScale),r.uniform4fv(o.uFaceA,c.faceA),r.uniform4fv(o.uFaceB,c.faceB),r.uniform4fv(o.uFaceC,c.faceC),r.uniform4fv(o.uFaceD,c.faceD),r.uniform3fv(o.uGlow,c.glow),r.uniform3fv(o.uShadow,e.shadow),r.uniform1f(o.uFloor,e.floor),r.uniform1f(o.uLift,l),r.uniform1f(o.uExposure,e.exposure*c.exposure),r.uniform3fv(o.uAlbedo,e.albedo),r.uniform1f(o.uGlowPool,s.glowPool??0),r.uniform4fv(o.uFxA,e.fx.a),r.uniform4fv(o.uFxB,e.fx.b),r.uniform4fv(o.uFxC,e.fx.c),r.uniform1i(o.uFxCount,e.fx.count),r.drawArrays(r.TRIANGLES,0,3),this.target.globalCompositeOperation=`copy`,this.target.drawImage(n.canvas,0,n.canvas.height-a,i,a,0,0,i,a),!0}dispose(){this.character=null}},je=/^#[0-9a-f]{6}$/i;function Me(e,t,n,r){if(!t.includes(n))throw Error(`${e}: palette names material "${n}". Materials are: ${t.join(`, `)}.`);if(!je.test(r))throw Error(`${e}: palette colour for "${n}" must look like #rrggbb, got "${r}".`)}function Ne(e,t){let n=Object.keys(e.materials),r=new Map;for(let[i,a]of Object.entries(t))Me(e.id,n,i,a),r.set(i,F(a));for(let[n,i]of Object.entries(e.materials)){let a=i.shadeOf;if(!a||r.has(n)||!(a in t))continue;let o=F(e.materials[a].color),s=F(i.color),c=r.get(a);r.set(n,[0,1,2].map(e=>Math.min(1,o[e]>.001?c[e]*s[e]/o[e]:s[e])))}return r}function Pe(e,t){let n=e.albedo.slice();if(!t)return n;for(let[r,i]of Ne(e.spec,t))n.set(i,e.materials.indexOf(r)*3);return n}var Fe=new class{members=new Set;frame=0;last=0;time=0;quality=1;slow=0;fast=0;add(e){this.members.add(e),this.start()}delete(e){this.members.delete(e),this.members.size||this.stop()}start(){this.frame||typeof requestAnimationFrame>`u`||(this.last=performance.now(),this.frame=requestAnimationFrame(this.loop))}stop(){cancelAnimationFrame(this.frame),this.frame=0}loop=e=>{this.frame=requestAnimationFrame(this.loop);let t=Math.max(0,e-this.last),n=Math.min(t/1e3,1/20);this.adapt(t),this.last=e,this.time+=n;for(let e of this.members)e.active&&e.tick(n,this.time,this.quality)};adapt(e){e>22&&e<200?this.slow++:this.slow=Math.max(0,this.slow-1),e<17.5?this.fast++:this.fast=0,this.slow>20?(this.quality=Math.max(.55,this.quality*.85),this.slow=0):this.fast>120&&this.quality<1&&(this.quality=Math.min(1,this.quality*1.08),this.fast=0)}},Ie=new WeakMap;function Le(e){let t=Ie.get(e);return t||Ie.set(e,t=he(e)),t}var Re=class{constructor(e,t,n={}){if(this.canvas=e,this.seed=n.seed??Math.random(),this.palette=n.palette,this.options={interactive:n.interactive??!0,effects:n.effects??!0,speed:n.speed??1,maxPixelRatio:n.maxPixelRatio??2,shadow:n.shadow??[.05,.06,.12],floor:n.floor??1,exposure:n.exposure??1,framing:n.framing??1,respectReducedMotion:n.respectReducedMotion??!0},this.renderer=new Ae(e),this.load(t,n.state??`idle`),e.setAttribute(`role`,`img`),this.reducedMotion=typeof matchMedia==`function`?matchMedia(`(prefers-reduced-motion: reduce)`):null,typeof IntersectionObserver<`u`){let t=new IntersectionObserver(([e])=>this.visible=e.isIntersecting);t.observe(e),this.cleanup.push(()=>t.disconnect())}this.options.interactive&&this.listen(),Fe.add(this)}canvas;character;brain;rig;fx;renderer;options;seed;palette;albedo;visible=!0;paused=!1;time=0;reducedMotion;stillFrames=0;drawn=!1;listeners={poke:new Set,state:new Set,ready:new Set};cleanup=[];source;get state(){return this.brain.state}get spec(){return this.source}get stats(){return this.character.stats}setState(e){if(!C.includes(e))throw Error(`Unknown state "${e}". Expected one of ${C.join(`, `)}.`);e!==this.brain.state&&(this.brain.setState(e),this.stillFrames=0,this.label(),this.emit(`state`,e))}setSpec(e,t){this.palette=t,this.load(e,this.brain.state)}setPalette(e){this.albedo=Pe(this.character,e),this.palette=e,this.stillFrames=0}setSpeed(e){this.options.speed=Math.max(0,e)}setEffects(e){this.options.effects=e}poke(){this.brain.poke(),this.stillFrames=0,this.emit(`poke`,void 0)}pause(){this.paused=!0}play(){this.paused=!1}on(e,t){return this.listeners[e].add(t),()=>this.listeners[e].delete(t)}get active(){return!this.visible||this.paused?!1:!this.still||this.stillFrames<2}tick(e,t,n){let r=this.still,i=e*this.options.speed;if(r)for(let e=0;e<90;e++)this.brain.update(1/60);else this.brain.update(i),this.time+=i;let a=r?0:this.time,o=this.brain.pose;this.rig.update(o.root,o.channels,o.weights,a,r?0:i),!r&&this.options.effects?this.fx.update(i,o,this.rig):this.fx.count=0,o.events.length=0;let s=Math.min(devicePixelRatio||1,this.options.maxPixelRatio)*n,c=this.renderer.render({pose:o,bones:this.rig.inverse,fx:this.fx,albedo:this.albedo,time:a,width:Math.max(1,Math.round(this.canvas.clientWidth*s)),height:Math.max(1,Math.round(this.canvas.clientHeight*s)),shadow:this.options.shadow,floor:this.options.floor,exposure:this.options.exposure,framing:this.options.framing});c&&r&&this.stillFrames++,c&&!this.drawn&&(this.drawn=!0,this.emit(`ready`,void 0))}get ready(){return this.drawn}dispose(){Fe.delete(this),this.cleanup.forEach(e=>e()),this.listeners.poke.clear(),this.listeners.state.clear(),this.listeners.ready.clear(),this.renderer.dispose()}load(e,t){this.source=e,this.character=Le(e),this.albedo=Pe(this.character,this.palette),this.renderer.load(this.character),this.brain=new A(e.motion,this.seed),this.brain.setState(t),this.rig=new we(this.character.bones,this.character.acting),this.fx=new te(this.character,v(this.seed+.37)),this.stillFrames=0,this.label()}get still(){return this.options.respectReducedMotion&&(this.reducedMotion?.matches??!1)}emit(e,t){for(let n of this.listeners[e])n(t)}label(){this.canvas.hasAttribute(`data-own-label`)||this.canvas.setAttribute(`aria-label`,`${this.source.name}, ${this.brain.state}`)}listen(){let e=e=>{let t=this.canvas.getBoundingClientRect(),n=Math.max(t.width,1),r=(e.clientX-(t.left+t.width/2))/(n*1.1),i=(e.clientY-(t.top+t.height*.45))/(n*1.1);this.brain.pointer=Math.hypot(r,i)<3?{x:r,y:i}:null},t=()=>this.brain.pointer=null,n=()=>this.poke();window.addEventListener(`pointermove`,e,{passive:!0}),document.addEventListener(`pointerleave`,t),this.canvas.addEventListener(`click`,n),this.cleanup.push(()=>{window.removeEventListener(`pointermove`,e),document.removeEventListener(`pointerleave`,t),this.canvas.removeEventListener(`click`,n)})}};[...[[0,.2,.192],[.133,.21,-.145],[-.202,.22,.018],[.165,.229,.126],[-.037,.239,-.209],[-.117,.249,.184],[.215,.259,-.058],[-.202,.268,-.105],[.08,.278,.219],[.091,.288,-.22],[-.221,.298,.103],[.238,.308,.075],[-.128,.317,-.22],[-.056,.327,.254],[.218,.337,-.154],[-.272,.347,-.035],[.012,.366,-.281],[-.203,.376,.204],[.294,.386,-.014],[-.227,.396,-.19],[.172,.415,-.248],[-.301,.425,.068],[.269,.435,.154],[-.093,.444,-.293],[.292,.464,-.122],[-.299,.474,-.108],[.079,.493,-.301],[-.266,.503,.171],[.314,.513,.054],[-.191,.523,-.247],[.227,.542,-.21],[-.312,.552,.001],[.225,.562,.205],[-.027,.572,-.296],[.291,.591,-.053],[-.245,.601,-.154],[.074,.611,.27],[.126,.62,-.245],[-.256,.63,.095],[.246,.64,.1]].map(([e,t,n])=>({bone:`body`,on:[`berry`],kind:`sphere`,at:[e,t,n],radius:.022,color:`#ffd166`,soft:.2}))],[...[[0,.33,.05,.08],[-.22,.24,.2,.07],[.24,.22,.2,.065],[-.08,.2,.33,.055],[.12,.3,-.18,.07],[-.341,.196,-.136,.06],[.38,.173,-.058,.05]].map(([e,t,n,r])=>({bone:`cap`,on:[`cap`],kind:`sphere`,at:[e,t,n],radius:r,color:`#fff8ee`,soft:.12}))];var ze=[-.6,-.42,-.62];function Be(){let e={idle:{},thinking:{},listening:{},speaking:{},sleeping:{},working:{},error:{},surprised:{},celebrating:{},sad:{},happy:{}};for(let t=0;t<6;t++){let n=t*1.05;e.speaking[`t${t}s0`]={rx:[0,.2,1.1,n]},e.speaking[`t${t}s2`]={rx:[0,.35,1.6,n+1]},e.sleeping[`t${t}s0`]={rx:.3},e.sleeping[`t${t}s1`]={rx:.35},e.sleeping[`t${t}s2`]={rx:.55},e.happy[`t${t}s0`]={rx:[-.45,.35,2.4,n]},e.happy[`t${t}s1`]={rx:[0,.3,2.4,n+1]},e.error[`t${t}s0`]={rx:-.35},e.error[`t${t}s1`]={rx:[.35,.18,9,n]},e.error[`t${t}s2`]={rx:[.2,.22,11,n+2]},e.surprised[`t${t}s0`]={rx:-.85},e.surprised[`t${t}s1`]={rx:-.25},e.surprised[`t${t}s2`]={rx:-.3},e.celebrating[`t${t}s0`]={rx:[-.5,.3,3,n]},e.celebrating[`t${t}s1`]={rx:[.15,.3,3,n+1]},e.celebrating[`t${t}s2`]={rx:[.2,.3,3,n+2]},e.sad[`t${t}s0`]={rx:.45},e.sad[`t${t}s1`]={rx:.42},e.sad[`t${t}s2`]={rx:[.55,.06,.4,n]},e.working[`t${t}s0`]={rx:[-.15,.08,1.2,n]}}return e.working.t0s0={rx:[-1.25,.22,5.5,0]},e.working.t0s1={rx:[.7,.2,5.5,.6]},e.working.t5s0={rx:[-1.25,.22,5.5,Math.PI]},e.working.t5s1={rx:[.7,.2,5.5,Math.PI+.6]},e.celebrating.t0s0={rx:-.3,rz:[1.05,.25,3.2,0]},e.celebrating.t0s1={rx:[.5,.15,3.2,1]},e.celebrating.t0s2={rx:[.6,.2,3.2,2]},e.celebrating.t5s0={rx:-.3,rz:[-1.05,.25,3.2,Math.PI]},e.celebrating.t5s1={rx:[.5,.15,3.2,Math.PI+1]},e.celebrating.t5s2={rx:[.6,.2,3.2,Math.PI+2]},e.thinking.t0s0={rx:-1.75},e.thinking.t0s1={rx:.95},e.thinking.t0s2={rx:[1,.12,1.6,0]},e.listening.t5s0={rx:-1.6},e.listening.t5s1={rx:-.2},e.listening.t5s2={rx:.7},e}var Ve=[{name:`mantle`,pivot:[0,.42,0],drive:{rx:[[`pitch`,-.6]],ry:[[`yaw`,.6]],rz:[[`roll`,.6]]}}];for(let e=0;e<6;e++){let t=(e+.5)/6*Math.PI*2;for(let n=0;n<3;n++){let r=`t${e}s${n}`;Ve.push({name:r,parent:n===0?`mantle`:`t${e}s${n-1}`,pivot:n===0?[.26*Math.sin(t),.02,.26*Math.cos(t)]:[0,-.17,0],rest:n===0?{rx:ze[0],ry:t}:{rx:ze[n]},wave:{rx:[.12+n*.1,.32,e*1.3+n*.8],rz:[.06+n*.05,.21,e*2.1+n]},jiggle:{axis:[0,-1,0],length:.17,freq:2.4-n*.4,damping:.25,maxAngle:.8}})}}[...[[.14,.78,.12,.07],[-.2,.72,.16,.055],[.33,.6,.12,.05],[-.04,.83,-.05,.06],[-.36,.52,.1,.05],[.06,.62,.33,.045],[.338,.425,-.291,.045]].map(([e,t,n,r])=>({bone:`mantle`,on:[`skin`],kind:`sphere`,at:[e,t,n],radius:r,color:`#d23f6c`,soft:.2}))],Be();var He=Math.PI/2;[...[[`legL`,`shinL`,-1],[`legR`,`shinR`,1]].flatMap(([e,t,n])=>[{bone:e,shape:`roundBox`,at:[0,-.075,0],half:[.038,.07,.042],round:.015,material:`servo`},{bone:e,shape:`cylinder`,at:[0,-.15,0],rot:[0,0,He],radius:.036,half:.05,round:.012,material:`horn`},{bone:e,shape:`plate`,at:[n*.056,-.1,-.005],rot:[n*He,n*Math.PI/4,He],half:[.058,.058],corner:.034,depth:.012,material:`bodyShell`},{bone:t,shape:`roundBox`,at:[0,-.06,0],half:[.034,.055,.038],round:.014,material:`servo`},{bone:t,shape:`roundBox`,at:[0,-.135,.005],half:[.048,.036,.052],round:.016,material:`servo`},{bone:t,shape:`roundBox`,at:[0,-.17,.045],half:[.074,.04,.108],round:.038,material:`boot`},{bone:t,shape:`roundBox`,at:[0,-.196,.045],half:[.079,.014,.113],round:.012,material:`sole`}])],[...[-1,1].flatMap(e=>[{bone:`head`,on:[`bill`],kind:`sphere`,at:[e*.208,.085,-.13],radius:.013,color:`#c8261a`,soft:.2},{bone:`head`,on:[`bill`],kind:`sphere`,at:[e*.208,.085,-.18],radius:.013,color:`#c8261a`,soft:.2}]),...[`shinL`,`shinR`].flatMap(e=>[[-.03,.1],[.03,.1],[0,.13],[-.03,.06],[.03,.06]].map(([t,n])=>({bone:e,on:[`boot`],kind:`sphere`,at:[t,-.13,n],radius:.011,color:`#c23a14`,soft:.25}))),...[-1,1].map(e=>({bone:`body`,on:[`bodyShell`],kind:`sphere`,at:[e*.142,.04,.117],radius:.009,color:`#8d9198`,soft:.2}))];var Ue=[{parent:`head`,at:[0,.43,.05],tilt:-.1,size:.075},{parent:`head`,at:[0,.41,-.1],tilt:-.5,size:.09},{parent:`head`,at:[0,.3,-.24],tilt:-1,size:.085},{parent:`body`,at:[0,.5,-.24],tilt:-1.2,size:.08},{parent:`body`,at:[0,.34,-.3],tilt:-1.45,size:.07},{parent:`tail0`,at:[0,.12,.07],tilt:0,size:.06},{parent:`tail1`,at:[0,.1,.05],tilt:0,size:.045}];[...Ue.map(({parent:e,at:t,tilt:n},r)=>({name:`spike${r}`,parent:e,pivot:t,rest:{rx:n},jiggle:{axis:[0,1,0],length:.08,freq:4+r*.3,damping:.12,maxAngle:.45}}))],[...[-1,1].flatMap(e=>[{bone:`body`,shape:`ellipsoid`,at:[e*.2,.045,.1],radii:[.1,.05,.13],blend:.05,material:`bodyHide`},...[-1,0,1].map(t=>({bone:`body`,shape:`ellipsoid`,at:[e*.2+t*.05,.03,.225-Math.abs(t)*.015],radii:[.022,.022,.026],blend:.012,material:`claw`}))]),...[[`armL`,-1],[`armR`,1]].flatMap(([e,t])=>[{bone:e,shape:`capsule`,from:[0,0,0],to:[t*.01,-.1,.03],radius:.042,blend:.04,material:`bodyHide`},{bone:e,shape:`sphere`,at:[t*-.014,-.135,.05],radius:.015,blend:.01,material:`claw`},{bone:e,shape:`sphere`,at:[t*.02,-.135,.045],radius:.015,blend:.01,material:`claw`}]),...Ue.map(({size:e},t)=>({bone:`spike${t}`,shape:`roundCone`,from:[0,-.02,0],to:[0,e*1.1,0],r1:e*.65,r2:e*.15,blend:.025,material:`spike`}))],[...[[-.083,.204,.289],[-.109,.181,.297],[.083,.204,.289],[.109,.181,.297]].map(([e,t,n])=>({bone:`head`,on:[`hide`],kind:`sphere`,at:[e,t,n],radius:.009,color:`#3f8a4f`,soft:.3}))];function We(e){let t=e<0?`L`:`R`;return[{name:`shoulder${t}`,parent:`body`,pivot:[.385*e,.47,.02],drive:{rz:[[`flap`,.5*e]]}},{name:`fore${t}`,parent:`shoulder${t}`,pivot:[0,-.17,0],jiggle:{axis:[0,-1,0],length:.16,freq:3.2,damping:.35,maxAngle:.3}}]}function Ge(e){let t=e<0?`L`:`R`;return[{bone:`shoulder${t}`,shape:`sphere`,radius:.074,material:`trim`},{bone:`shoulder${t}`,shape:`capsule`,from:[0,-.02,0],to:[0,-.15,0],radius:.058,material:`shell`},{bone:`fore${t}`,shape:`sphere`,radius:.052,material:`trim`},{bone:`fore${t}`,shape:`capsule`,from:[0,-.02,0],to:[0,-.12,0],radius:.052,material:`shell`},{bone:`fore${t}`,shape:`sphere`,at:[0,-.175,0],radius:.066,material:`trim`},{bone:`fore${t}`,shape:`sphere`,op:`sub`,blend:.012,at:[0,-.235,.012],radius:.036,material:`trim`}]}function Ke(e){let t=e<0?`L`:`R`;return[{bone:`ear${t}`,shape:`cylinder`,rot:[0,0,1.5708],radius:.112,half:.03,round:.018,material:`trim`},{bone:`ear${t}`,shape:`cylinder`,at:[.045*e,0,0],rot:[0,0,1.5708],radius:.058,half:.035,round:.018,material:`trim`},{bone:`ear${t}`,shape:`sphere`,at:[.035*e,.078,0],radius:.02,material:`metal`},{bone:`ear${t}`,shape:`sphere`,at:[.035*e,-.078,0],radius:.02,material:`metal`}]}var qe={id:`volt`,name:`Volt`,tagline:`LED face, claw hands, gear ears, a sprung antenna`,accent:`#3b63d9`,frame:{target:.86,radius:1.02},bound:{y:.86,radius:1.12},motion:{hop:.16,squash:1,snap:1},glowPool:.35,materials:{shell:{color:`#2f56c4`,f0:.05,spec:.7,shininess:70,rim:.55,gloss:.55},trim:{color:`#c3cce3`,f0:.07,spec:.8,shininess:90,metal:.25,rim:.4,gloss:.5},metal:{color:`#8f98ae`,f0:.45,spec:1,shininess:120,metal:.85,rim:.3,gloss:.7},rubber:{color:`#151a28`,f0:.03,spec:.15,shininess:12,rim:.2},screen:{color:`#03060c`,f0:.045,spec:1.6,shininess:260,rim:.1,gloss:1},bulb:{color:`#f2f5ff`,f0:.04,spec:.6,shininess:40,rim:.3,glows:!0,emitStrength:1.4,sss:.4,sssColor:`#ffffff`},lamp:{color:`#e9eeff`,f0:.05,spec:1,shininess:80,glows:!0,emitStrength:1.1,gloss:.9},ring:{color:`#d8e4ff`,f0:.04,spec:.4,shininess:30,glows:!0,emitStrength:1.6}},bones:[{name:`body`,pivot:[0,0,0],drive:{ry:[[`yaw`,.2]],rz:[[`roll`,.25]]}},{name:`head`,parent:`body`,pivot:[0,.64,0],drive:{rx:[[`pitch`,-1]],ry:[[`yaw`,.8]],rz:[[`roll`,.75]]}},{name:`antenna`,parent:`head`,pivot:[0,.755,0],jiggle:{axis:[0,1,0],length:.26,freq:2.3,damping:.11}},{name:`earL`,parent:`head`,pivot:[-.585,.37,0]},{name:`earR`,parent:`head`,pivot:[.585,.37,0]},...We(-1),...We(1)],parts:[{bone:`body`,shape:`roundBox`,at:[0,.32,0],half:[.35,.27,.28],round:.22,material:`shell`},{bone:`body`,shape:`roundBox`,at:[0,.38,.27],half:[.15,.08,.03],round:.06,material:`rubber`},{bone:`body`,shape:`sphere`,at:[0,.38,.285],radius:.04,material:`lamp`},{bone:`body`,shape:`plate`,op:`sub`,blend:.006,at:[0,.225,.3],half:[.075,.009],corner:.009,depth:.03,material:`shell`},{bone:`body`,shape:`plate`,op:`sub`,blend:.006,at:[0,.19,.295],half:[.075,.009],corner:.009,depth:.03,material:`shell`},{bone:`body`,shape:`plate`,op:`sub`,blend:.006,at:[0,.155,.27],half:[.06,.009],corner:.009,depth:.03,material:`shell`},{bone:`body`,shape:`roundBox`,at:[-.17,.035,.05],half:[.11,.035,.14],round:.035,material:`trim`},{bone:`body`,shape:`roundBox`,at:[.17,.035,.05],half:[.11,.035,.14],round:.035,material:`trim`},{bone:`body`,shape:`cylinder`,at:[0,.62,0],radius:.075,half:.06,round:.02,material:`metal`},{bone:`head`,shape:`roundBox`,at:[0,.37,0],half:[.56,.37,.35],round:.17,material:`shell`},{bone:`head`,shape:`roundBox`,op:`sub`,blend:.035,at:[0,.37,.41],half:[.45,.28,.1],round:.12,material:`shell`},{bone:`head`,shape:`plate`,at:[0,.37,.31],half:[.45,.28],corner:.12,depth:.012,material:`screen`},{bone:`head`,shape:`cylinder`,at:[-.555,.37,0],rot:[0,0,1.5708],radius:.122,half:.012,round:.006,material:`ring`},{bone:`head`,shape:`cylinder`,at:[.555,.37,0],rot:[0,0,1.5708],radius:.122,half:.012,round:.006,material:`ring`},...Ke(-1),...Ke(1),{bone:`head`,shape:`cylinder`,at:[0,.745,0],radius:.065,half:.025,round:.012,material:`trim`},{bone:`antenna`,shape:`capsule`,from:[0,0,0],to:[0,.2,0],radius:.016,material:`metal`},{bone:`antenna`,shape:`sphere`,at:[0,.25,0],radius:.055,material:`bulb`},...Ge(-1),...Ge(1)],face:{kind:`screen`,bone:`head`,material:`screen`,center:[0,.37],half:[.44,.27],corner:.11,cell:.034,color:`#c4ecff`},anchors:{top:{bone:`head`,at:[.3,.78,.1]},mouth:{bone:`head`,at:[0,.22,.34]},ear:{bone:`head`,at:[-.66,.37,0]},feet:{bone:`root`,at:[0,.02,.06]},antenna:{bone:`antenna`,at:[0,.25,0]}},acting:{idle:{shoulderL:{rz:[-.08,.04,.45,0],rx:[0,.06,.35,1]},shoulderR:{rz:[.08,.04,.45,1.6],rx:[0,.06,.35,2.4]},foreL:{rx:-.25},foreR:{rx:-.25}},thinking:{shoulderR:{rx:-1.5,ry:-.8,rz:-.1},foreR:{rx:[-.95,.1,1.8,0]},shoulderL:{rx:-1,ry:.8,rz:-.3},foreL:{rx:-.8},earL:{rx:[0,0,0,0,5]},earR:{rx:[0,0,0,0,-5]}},listening:{shoulderL:{rx:.1,ry:.3,rz:-2.8},foreL:{rx:-.6},shoulderR:{rz:.14,rx:.05},foreR:{rx:-.3},earL:{rx:[.3,.15,.8,0]}},speaking:{shoulderL:{rx:[-.55,.32,.72,0],rz:[-.28,.12,.5,0]},foreL:{rx:[-.85,.38,1.44,.6]},shoulderR:{rx:[-.45,.32,.72,2.2],rz:[.28,.12,.5,1]},foreR:{rx:[-.95,.38,1.44,2.8]},earL:{rx:[0,0,0,0,1.4]},earR:{rx:[0,0,0,0,-1.4]}},sleeping:{shoulderL:{rz:-.03,rx:-.3},shoulderR:{rz:.03,rx:-.3},foreL:{rx:-.4},foreR:{rx:-.4}},working:{shoulderL:{rx:-.85,rz:-.12},shoulderR:{rx:-.85,rz:.12},foreL:{rx:[-.95,.2,6,0]},foreR:{rx:[-.95,.2,6,Math.PI]},earL:{rx:[0,0,0,0,3]},earR:{rx:[0,0,0,0,-3]}},error:{shoulderL:{rz:[-.95,.1,11,0],rx:-.2},shoulderR:{rz:[.95,.1,11,1],rx:-.2},foreL:{rx:-1.1},foreR:{rx:-1.1}},surprised:{shoulderL:{rz:-1.55,rx:-.3},shoulderR:{rz:1.55,rx:-.3},foreL:{rx:-.35},foreR:{rx:-.35}},celebrating:{shoulderL:{rz:[-2.55,.28,4,0]},shoulderR:{rz:[2.55,.28,4,Math.PI]},foreL:{rz:[.2,.4,8,0]},foreR:{rz:[-.2,.4,8,Math.PI]},earL:{rx:[0,0,0,0,12]},earR:{rx:[0,0,0,0,-12]}},sad:{shoulderL:{rz:.04,rx:.22},shoulderR:{rz:-.04,rx:.22},foreL:{rx:-.05},foreR:{rx:-.05}},happy:{shoulderL:{rz:[-2.5,.22,2.2,0]},foreL:{rz:[.1,.5,4.2,0]},shoulderR:{rz:[2.5,.22,2.2,1.5]},foreR:{rz:[-.1,.5,4.2,2]},earL:{rx:[0,0,0,0,10]},earR:{rx:[0,0,0,0,-10]}}},fx:{replace:[`syllable`],syllable:[{glyph:`arc`,anchor:`mouth`,rate:2,offset:[.5,.1,-.1],mirror:!0,velocity:[.26,.02,.02],jitter:.02,life:[.55,.7],size:[.04,.1],rotation:0,color:`#6aaee6`}],thinking:[{glyph:`ring`,anchor:`antenna`,rate:1.3,velocity:[0,.02,0],life:[.9,1.1],size:[.03,.17],color:`#ffb347`,glow:!0}],listening:[{glyph:`ring`,anchor:`antenna`,rate:1.1,velocity:[0,0,0],life:[1,1.2],size:[.2,.03],color:`#62e39a`,glow:!0}],land:[{glyph:`spark`,anchor:`feet`,rate:6,spread:.12,velocity:[0,.6,0],jitter:1.1,gravity:3,life:[.25,.42],size:[.035,.02],color:`#ffd27a`,glow:!0,align:!0}],"enter:happy":[{glyph:`spark`,anchor:`antenna`,rate:8,velocity:[0,.5,0],jitter:1.4,gravity:2,life:[.3,.5],size:[.04,.02],color:`#ffe08a`,glow:!0,align:!0}]}},Je={shell:`#f6fbff`,trim:`#52ccdf`,lamp:`#8df6ff`,bulb:`#8df6ff`,ring:`#8df6ff`};function Ye(e){let t=()=>document.dispatchEvent(new Event(`pointerleave`)),n=n=>{let r=e.getBoundingClientRect();(n.clientX<r.left-24||n.clientX>r.right+24||n.clientY<r.top-24||n.clientY>r.bottom+24)&&t()};return window.addEventListener(`pointermove`,n,{passive:!0}),window.addEventListener(`blur`,t),()=>{window.removeEventListener(`pointermove`,n),window.removeEventListener(`blur`,t)}}var $=n();function Xe({state:e}){let t=(0,r.useRef)(null),n=(0,r.useRef)(null),i=(0,r.useRef)(e),a=(0,r.useRef)(void 0),[o,s]=(0,r.useState)(`loading`);(0,r.useEffect)(()=>{if(!t.current)return;let e;try{e=new Re(t.current,qe,{state:i.current,palette:Je,maxPixelRatio:1,framing:1.05,floor:0})}catch{let e=window.setTimeout(()=>s(`fallback`),0);return()=>window.clearTimeout(e)}n.current=e;let r=Ye(t.current),o=window.setTimeout(()=>{e.pause(),s(`fallback`)},1e4),c=e.on(`ready`,()=>{window.clearTimeout(o),s(`webgl`)});return()=>{window.clearTimeout(o),window.clearTimeout(a.current),c(),r(),e.dispose(),n.current=null}},[]),(0,r.useEffect)(()=>{window.clearTimeout(a.current),n.current?.setState(e)},[e]);let[c,l]=(0,r.useState)({x:0,y:0}),[u,d]=(0,r.useState)(!1),f=(0,r.useRef)(null);function p(){n.current&&(window.clearTimeout(a.current),n.current.setState(`celebrating`),a.current=window.setTimeout(()=>n.current?.setState(e),4e3))}function m(e){if(e.button!==0)return;let t=e.currentTarget,n=t.closest(`.avatar-assistant`)||t.parentElement,r=-280,i=100,a=-85,o=85;if(n){let e=n.getBoundingClientRect();r=-Math.max(240,Math.round(e.height*.48));let t=Math.max(60,Math.round(e.height*.18));i=Math.min(120,t);let s=Math.max(65,Math.round(e.width*.22));a=-s,o=s}f.current={startX:e.clientX,startY:e.clientY,origX:c.x,origY:c.y,moved:!1,minX:a,maxX:o,minY:r,maxY:i},d(!0),t.setPointerCapture(e.pointerId)}function h(e){if(!f.current)return;let t=e.clientX-f.current.startX,n=e.clientY-f.current.startY;if(!f.current.moved&&Math.hypot(t,n)>4&&(f.current.moved=!0),f.current.moved){let{minX:e,maxX:r,minY:i,maxY:a}=f.current,o=Math.max(e,Math.min(r,f.current.origX+t)),s=Math.max(i,Math.min(a,f.current.origY+n));l({x:o,y:s})}}function g(e){if(f.current){f.current.moved||n.current?.poke(),f.current=null,d(!1);try{e.currentTarget.releasePointerCapture(e.pointerId)}catch{}}}function _(){f.current=null,d(!1)}return(0,$.jsx)(`div`,{className:`assistant-pet ${u?`is-dragging`:``}`,"data-state":e,"data-renderer":o,style:{transform:`translate3d(${c.x}px, ${c.y}px, 0)`},onPointerDown:m,onPointerMove:h,onPointerUp:g,onPointerCancel:_,onDoubleClick:p,children:(0,$.jsxs)(`div`,{className:`pet-floating-body`,children:[o!==`webgl`&&(0,$.jsx)(`img`,{className:`pet-fallback`,src:`/pet/volt-${e}.webp`,alt:`Volt`,draggable:!1}),(0,$.jsx)(`canvas`,{ref:t,className:`pet-webgl`,hidden:o===`fallback`})]})})}export{Xe as default};