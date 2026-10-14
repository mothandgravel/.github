import React, {useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, Audio, Composition, Img, interpolate, registerRoot, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {activeCaption, clock, videoDuration} from './timeline.mjs';

const colors = {charcoal: '#17191b', paper: '#f1eee6', brass: '#dfc195', muted: '#c6c0b6', line: '#f1eee62b'};
const mono = '"Liberation Mono", Consolas, monospace';
const condensed = '"Arial Narrow", "Liberation Sans Narrow", "Helvetica Neue", Arial, sans-serif';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};

const FieldNote = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const fade = interpolate(time, [0, 0.7], [0, 1], clamp);
  const settle = interpolate(time, [0, 1.6], [28, 0], clamp);
  const ending = time >= props.duration - props.outro;
  const light = Math.sin(time / 27) * props.video.width * 0.03;
  const caption = activeCaption(props.pages, time);
  const progress = Math.min(1, time / props.duration);
  const titleSize = props.title.length > 55 ? 82 : props.title.length > 35 ? 96 : 116;
  const heading = useRef(null);
  useLayoutEffect(() => {
    // Fit the actual installed font and line breaks, rather than title length.
    const block = heading.current;
    const title = block.querySelector('h1');
    let size = titleSize;
    title.style.fontSize = `${size}px`;
    while (block.offsetHeight > block.parentElement.clientHeight && size > 64) {
      size -= 2;
      title.style.fontSize = `${size}px`;
    }
  }, [props.title, titleSize]);
  useLayoutEffect(() => {
    for (const element of document.querySelectorAll('[data-fit-check]')) {
      const box = element.getBoundingClientRect();
      const parent = element.parentElement.getBoundingClientRect();
      if (box.top < parent.top - 2 || box.bottom > parent.bottom + 2 || box.left < parent.left - 2 || box.right > parent.right + 2) {
        throw new Error(`${element.dataset.fitCheck} does not fit the video layout`);
      }
    }
  }, [caption, props.thumbnail]);
  return (
    <AbsoluteFill style={{background: colors.charcoal, color: colors.paper, fontFamily: condensed}}>
      <Audio src={staticFile('master.wav')} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 66% 24%, #dfc19513, transparent 64%)', transform: `translateX(${light}px)`}} />
      <AbsoluteFill style={{width: 1920, height: 1080, padding: '64px 88px 52px', opacity: fade, transformOrigin: 'top left', transform: `scale(${props.video.width / 1920}) translateY(${settle}px)`}}>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 72, borderBottom: `1px solid ${colors.line}`, paddingBottom: 28}}>
          <div style={{display: 'flex', gap: 20, alignItems: 'center'}}>
            <Img src={staticFile('mark.svg')} style={{width: 58, height: 58, objectFit: 'contain'}} />
            <span style={{fontWeight: 800, letterSpacing: 3, fontSize: 28}}>MOTH <span style={{color: colors.brass}}>&</span> GRAVEL</span>
          </div>
          <span style={{fontFamily: mono, fontSize: 17, letterSpacing: 2, color: colors.muted}}>{props.label} / LISTENING EDITION</span>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: '1.02fr 1fr', gap: 82, height: 632, alignItems: 'center'}}>
          <div ref={heading} data-fit-check="Episode heading" style={{minWidth: 0}}>
            <p style={{fontFamily: mono, letterSpacing: 3, fontSize: 18, color: colors.brass, margin: '0 0 30px'}}>FIELD NOTES / {props.kind === 'note' ? 'FROM THE WORKBENCH' : props.kind.toUpperCase()}</p>
            <h1 style={{fontSize: titleSize, fontWeight: 800, lineHeight: 1.04, letterSpacing: -3.5, margin: '0 0 34px', textTransform: 'uppercase', overflowWrap: 'anywhere'}}>{props.title}</h1>
            <div style={{height: 2, width: 86, background: colors.brass, marginBottom: 26}} />
            <p style={{fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 31, lineHeight: 1.45, color: colors.muted, margin: 0}}>{ending ? 'Drawn to light. Built for rough ground.' : 'Curious questions. Working answers.'}</p>
          </div>
          <div style={{position: 'relative', height: 498, border: `1px solid ${colors.line}`, padding: 14, boxShadow: '18px 22px 0 -7px #af98701c', transform: `perspective(1800px) rotateY(${-2 + Math.sin(time / 40) * 0.2}deg)`}}>
            <Img src={staticFile(props.artwork)} style={{width: '100%', height: '100%', objectFit: 'contain', background: '#111415'}} />
            <div style={{position: 'absolute', bottom: 20, right: 20, padding: '8px 12px', background: '#17191bdd', color: colors.muted, fontFamily: mono, fontSize: 14}}>{props.artworkLabel}</div>
          </div>
        </div>
        <div style={{height: 154, borderTop: `1px solid ${colors.line}`, paddingTop: 27, display: 'flex', alignItems: 'flex-start', gap: 40}}>
          <span style={{fontFamily: mono, color: colors.brass, fontSize: 21, minWidth: 82, paddingTop: 4}}>{props.thumbnail ? 'READ / LISTEN' : clock(time)}</span>
          <div data-fit-check="Caption or thumbnail summary" style={{fontFamily: '"Helvetica Neue", Arial, sans-serif', fontSize: props.thumbnail ? 28 : 34, lineHeight: props.thumbnail ? 1.35 : 1.45, color: colors.paper, maxWidth: 1420, minWidth: 0, flex: 1, overflowWrap: 'anywhere'}}>
            {props.thumbnail ? props.description : caption || (ending ? 'More Field Notes at mothandgravel.com/notes' : time < props.intro ? 'An AI-narrated edition from Moth & Gravel.' : '')}
          </div>
        </div>
        <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: mono, color: colors.muted, fontSize: 16, letterSpacing: 1.5}}>
          <span>MOTHANDGRAVEL.COM / FIELD NOTES</span><span>AI-NARRATED · MACHINE-GENERATED CAPTIONS</span>
        </div>
      </AbsoluteFill>
      {!props.thumbnail && <div style={{position: 'absolute', bottom: 0, left: 0, width: `${progress * 100}%`, height: 3, background: colors.brass}} />}
      {props.thumbnail && props.pages.map((page, index) => (
        <div key={index} style={{position: 'absolute', left: 0, top: 0, width: 1420, height: 126, visibility: 'hidden', pointerEvents: 'none'}}>
          <div data-fit-check={`Caption page ${index + 1}`} style={{fontFamily: '"Helvetica Neue", Arial, sans-serif', fontSize: 34, lineHeight: 1.45, overflowWrap: 'anywhere'}}>{page.text}</div>
        </div>
      ))}
    </AbsoluteFill>
  );
};

const Root = () => (
  <Composition id="FieldNote" component={FieldNote} durationInFrames={240} fps={24} width={1920} height={1080}
    calculateMetadata={({props}) => ({
      durationInFrames: videoDuration(props.duration, props.previewSeconds, props.video.fps),
      fps: props.video.fps, width: props.video.width, height: props.video.height,
    })}
  />
);

registerRoot(Root);
