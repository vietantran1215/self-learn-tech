import { useEffect, useRef, useState, type FormEvent } from 'react';
import { BookOpen, Plus, ArrowUp, FileText, Upload, MessageSquare, Sparkles, Presentation, Mic, X, ArrowLeft, Download, Check, LoaderCircle, LogOut, Leaf } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { request, stream, type Source } from './api';

type Notebook={id:string;title:string;owner:string};
type Document={id:string;name:string;status:string;error:string|null};
type Message={role:'user'|'assistant';content:string;sources?:Source[]};
type Question={question:string;answer:string;rubric:string[];citations:number[]};
type Quiz={questions:Question[];sources:Source[];demo:boolean};
type Deck={id:string;title:string;slides:{title:string;bullets:string[];citations:number[]}[];demo:boolean};

export default function App() {
  const [token,setToken]=useState(sessionStorage.getItem('token')||'');
  const [username,setUsername]=useState('alice'),[password,setPassword]=useState('learn-local');
  const [notebooks,setNotebooks]=useState<Notebook[]>([]),[active,setActive]=useState<Notebook|null>(null);
  const [documents,setDocuments]=useState<Document[]>([]),[messages,setMessages]=useState<Message[]>([]);
  const [question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState('');
  const [error,setError]=useState(''),[demo,setDemo]=useState(true),[newTitle,setNewTitle]=useState(''),[creating,setCreating]=useState(false);
  const [panel,setPanel]=useState<'quiz'|'deck'|null>(null),[topic,setTopic]=useState(''),[studioBusy,setStudioBusy]=useState(false);
  const [quiz,setQuiz]=useState<Quiz|null>(null),[deck,setDeck]=useState<Deck|null>(null),[revealed,setRevealed]=useState<number[]>([]);
  const [source,setSource]=useState<Source|null>(null);
  useEffect(()=>{
    if(!panel&&!source)return;
    const previous=document.activeElement as HTMLElement|null;
    const dialogs=document.querySelectorAll<HTMLElement>('[role="dialog"]');
    const dialog=dialogs[dialogs.length-1];
    const controls=()=>Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),input,textarea,select'));
    controls()[0]?.focus();
    const keyboard=(e:KeyboardEvent)=>{
      if(e.key==='Escape'){source?setSource(null):setPanel(null);return;}
      if(e.key!=='Tab')return;
      const elements=controls(),first=elements[0],last=elements[elements.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
    };
    document.addEventListener('keydown',keyboard);
    return ()=>{document.removeEventListener('keydown',keyboard);previous?.focus();};
  },[panel,source]);
  const uploadRef=useRef<HTMLInputElement>(null),bottomRef=useRef<HTMLDivElement>(null);
  const controllers=useRef(new Set<AbortController>());
  const history=useRef<Record<string,Message[]>>({});
  const ready=documents.some(d=>d.status==='ready');
  const abortAll=()=>{controllers.current.forEach(c=>c.abort());controllers.current.clear();};

  useEffect(()=>{fetch('/api/health').then(r=>r.json()).then(h=>setDemo(h.demo_mode)).catch(()=>setError('Start the API to connect your notebook.'));},[]);
  useEffect(()=>{
    if(!token) return;
    request<Notebook[]>('/notebooks',token).then(n=>{setNotebooks(n);setActive(n[0]||null);}).catch(e=>setError(e.message));
  },[token]);
  useEffect(()=>{
    abortAll(); setBusy(false);setStudioBusy(false);setStatus('');setDocuments([]);setQuiz(null);setDeck(null);setPanel(null);setSource(null);
    setMessages(active?history.current[active.id]||[]:[]);
    if(!active||!token)return;
    const controller=new AbortController();controllers.current.add(controller);
    let after=0;
    const refresh=()=>request<Document[]>(`/notebooks/${active.id}/documents`,token,{signal:controller.signal}).then(setDocuments);
    refresh().catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    const listen=async()=>{
      while(!controller.signal.aborted){
        try {await stream(`/notebooks/${active.id}/events?after=${after}`,token,{signal:controller.signal},e=>{
          after=Number(e.id||after);refresh().catch(()=>{});
        });} catch(e) {if(controller.signal.aborted)return;setError((e as Error).message);return;}
      }
    };
    void listen();
    return ()=>{controller.abort();controllers.current.delete(controller);};
  },[active?.id,token]);
  useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[messages,status]);

  async function login(e:FormEvent){
    e.preventDefault();setError('');
    try{const result=await request<{token:string}>('/login','',{method:'POST',body:JSON.stringify({username,password})});sessionStorage.setItem('token',result.token);setToken(result.token);}catch(e){setError((e as Error).message);}
  }
  async function create(e:FormEvent){
    e.preventDefault();if(!newTitle.trim())return;
    try{const n=await request<Notebook>('/notebooks',token,{method:'POST',body:JSON.stringify({title:newTitle})});setNotebooks(v=>[n,...v]);setActive(n);setNewTitle('');setCreating(false);}catch(e){setError((e as Error).message);}
  }
  async function upload(files:FileList|null){
    if(!files||!active)return;
    const notebook=active;
    setError('');
    for(const file of Array.from(files)){
      const body=new FormData();body.append('file',file);
      const controller=new AbortController();controllers.current.add(controller);
      try{const d=await request<Document>(`/notebooks/${notebook.id}/documents`,token,{method:'POST',body,signal:controller.signal});
        if(controller.signal.aborted)return;
        setDocuments(v=>v.some(x=>x.id===d.id)?v:[...v,d]);
      }catch(e){if((e as Error).name!=='AbortError')setError((e as Error).message);}
      finally{controllers.current.delete(controller);}
    }
    if(uploadRef.current)uploadRef.current.value='';
  }
  async function chat(text:string){
    if(!active||busy||!text.trim())return;
    const id=active.id,prior=messages.slice(-8),next:Message[]=[...messages,{role:'user',content:text},{role:'assistant',content:'',sources:[]}];
    const controller=new AbortController();controllers.current.add(controller);
    setQuestion('');setBusy(true);setError('');setMessages(next);
    try{await stream(`/notebooks/${id}/chat`,token,{method:'POST',body:JSON.stringify({question:text,history:prior.map(({role,content})=>({role,content}))}),signal:controller.signal},e=>{
      if(e.type==='status')setStatus(String(e.text));
      if(e.type==='sources')next[next.length-1].sources=e.sources as Source[];
      if(e.type==='token')next[next.length-1].content+=String(e.text);
      if(e.type==='error')throw new Error(String(e.text));
      setMessages(next.map(m=>({...m})));history.current[id]=next.map(m=>({...m}));
    });}catch(e){if((e as Error).name!=='AbortError')setError((e as Error).message);}finally{
      controllers.current.delete(controller);if(!controller.signal.aborted){setBusy(false);setStatus('');}
    }
  }
  async function studio(){
    if(!active||!panel||studioBusy)return;
    const controller=new AbortController();controllers.current.add(controller);
    setStudioBusy(true);setError('');setRevealed([]);
    try{
      const path=`/notebooks/${active.id}/${panel}`;
      const options={method:'POST',body:JSON.stringify({topic:topic||`Key ideas in ${active.title}`}),signal:controller.signal};
      if(panel==='quiz')setQuiz(await request<Quiz>(path,token,options));
      else setDeck(await request<Deck>(path,token,options));
    }catch(e){if((e as Error).name!=='AbortError')setError((e as Error).message);}finally{controllers.current.delete(controller);if(!controller.signal.aborted)setStudioBusy(false);}
  }
  async function download(){
    if(!deck)return;
    try{
      const response=await fetch('/api/artifacts/'+deck.id,{headers:{Authorization:'Bearer '+token}});
      if(!response.ok)throw new Error('Download failed');
      const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='study-deck.pptx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){setError((e as Error).message);}
  }
  const sourceButtons=(sources:Source[],numbers?:number[])=><div className="source-chips">{sources.map((s,i)=><button key={s.id} onClick={()=>setSource(s)}><span>{numbers?.[i]??i+1}</span>{s.name} · p. {s.page}</button>)}</div>;

  if(!token)return <main className="login"><div className="login-art"><div className="brand"><Leaf size={26}/> fieldnotes</div><span className="eyebrow">A LITTLE CURIOSITY GOES A LONG WAY</span><h1>Make room<br/>for your next<br/><em>big idea.</em></h1><p>Your sources. Your questions.<br/>A quieter place to learn something new.</p><div className="orb">✳</div></div><form onSubmit={login} className="login-form"><span className="eyebrow">YOUR LEARNING SPACE</span><h2>Welcome to Fieldnotes</h2><p>Explore the local development workspace.</p><label>Account<select value={username} onChange={e=>setUsername(e.target.value)}><option value="alice">Alice</option><option value="bob">Bob</option></select></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label><button className="primary" type="submit">Open my notebooks <ArrowUp size={18}/></button><small>Local accounts use the configured DEMO_PASSWORD. Each account has its own private notebooks.</small>{error&&<div className="error" role="alert">{error}</div>}</form></main>;

  return <div className="app-shell">
    <nav className="rail"><a className="brand" href="#" aria-label="Fieldnotes"><Leaf/> fieldnotes</a><div className="rail-label">YOUR NOTEBOOKS <button onClick={()=>setCreating(!creating)} aria-label="Create notebook"><Plus size={17}/></button></div>
      {creating&&<form className="new-form" onSubmit={create}><input autoFocus placeholder="Notebook title" maxLength={120} value={newTitle} onChange={e=>setNewTitle(e.target.value)}/><button type="submit" aria-label="Save notebook"><Check size={18}/></button></form>}
      <div className="notebook-list">{notebooks.map(n=><button className={active?.id===n.id?'selected':''} key={n.id} onClick={()=>setActive(n)}><BookOpen size={18}/><span>{n.title}</span></button>)}</div>
      <div className="rail-bottom"><div className="private-note"><span className="dot"/> A space of your own<p>Only your account can access these sources.</p></div><button onClick={()=>{abortAll();sessionStorage.removeItem('token');setToken('');setActive(null);setNotebooks([]);history.current={};}}><LogOut size={17}/> Sign out</button></div>
    </nav>
    <div className="workspace"><header><div><span className="breadcrumb">MY WORKSPACE / NOTEBOOK</span><h1>{active?.title||'Your learning space'}</h1></div><span className="mode"><span className="dot"/>{demo?'Demo mode':'Live models'}</span></header>
      {error&&<div className="error banner" role="alert">{error}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}
      {!active?<section className="first-notebook"><BookOpen size={42}/><h2>Every good question starts somewhere.</h2><p>Create a notebook, add your sources, and follow your curiosity.</p><form onSubmit={create}><input placeholder="What are you learning?" value={newTitle} onChange={e=>setNewTitle(e.target.value)} maxLength={120}/><button className="primary">Create notebook <Plus size={18}/></button></form></section>:
      <div className="columns"><aside className="sources-panel"><div className="section-heading"><h2>Sources</h2><span>{documents.length}</span></div><p className="muted">The starting point for every answer.</p><button className="upload-button" onClick={()=>uploadRef.current?.click()}><Plus size={18}/> Add sources</button><input hidden multiple type="file" ref={uploadRef} accept=".pdf,.txt,.md,.pptx,.png,.jpg,.jpeg" onChange={e=>void upload(e.target.files)}/>
        {!documents.length?<div className="upload-empty" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();void upload(e.dataTransfer.files);}}><Upload size={27}/><h3>A home for your material</h3><p>Drop files here or add a source above.</p><small>PDF, text, slides & images<br/>Up to 20 MB per file</small></div>:<div className="document-list">{documents.map(d=><article key={d.id}><FileText size={20}/><div><strong>{d.name}</strong><span className={'doc-status '+d.status}>{d.status==='ready'?<Check size={12}/>:d.status==='failed'?<X size={12}/>:<LoaderCircle className="spin" size={12}/>} {d.status}</span>{d.error&&<small>{d.error}</small>}{d.status==='failed'&&<button className="text-button" onClick={()=>request(`/notebooks/${active.id}/documents/${d.id}/retry`,token,{method:'POST'}).then(()=>setDocuments(v=>v.map(x=>x.id===d.id?{...x,status:'queued',error:null}:x))).catch(e=>setError(e.message))}>Retry upload</button>}</div></article>)}</div>}
        <div className="source-tip"><Sparkles size={17}/><p>{demo?'Demo mode searches text excerpts. Image understanding is available in live mode.':'Text and image descriptions are searched together, with source and page references.'}</p></div>
      </aside>
      <section className="chat-panel"><div className="chat-heading"><MessageSquare size={18}/><h2>Chat</h2><span>Grounded in your sources</span></div><div className="conversation">
        {!messages.length?<div className="chat-welcome"><div className="welcome-icon"><Sparkles size={32}/></div><span className="eyebrow">CONNECT THE DOTS</span><h2>What will you<br/><em>discover today?</em></h2><p>Ask a question, untangle a concept, or find the link between two ideas.</p><div className="suggestions">{['Give me an overview of the key ideas','Explain a concept with a practical example','Compare the main approaches in my sources'].map((s,i)=><button key={s} disabled={!ready} onClick={()=>void chat(s)}><span>0{i+1}</span>{s}<ArrowUp size={15}/></button>)}</div></div>:messages.map((m,i)=><article className={'message '+m.role} key={i}>{m.role==='assistant'&&<div className="assistant-label"><Leaf size={16}/> FIELDNOTES</div>}<ReactMarkdown>{m.content||'Searching your sources…'}</ReactMarkdown>{m.sources&&sourceButtons(m.sources)}</article>)}
        {status&&<div className="status"><LoaderCircle size={14} className="spin"/>{status}</div>}<div ref={bottomRef}/>
      </div><div className="composer-area"><form className="composer" onSubmit={e=>{e.preventDefault();void chat(question);}}><textarea aria-label="Ask about your sources" rows={2} placeholder={ready?'Ask anything about your sources…':'Add a source to start the conversation…'} value={question} onChange={e=>setQuestion(e.target.value)} disabled={!ready||busy} maxLength={4000} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void chat(question);}}}/><div><span>{documents.filter(d=>d.status==='ready').length} sources ready</span><button type="submit" disabled={!ready||busy||!question.trim()} aria-label="Send question">{busy?<LoaderCircle className="spin" size={18}/>:<ArrowUp size={20}/>}</button></div></form><small>{demo?'Demo answers are retrieved excerpts. Enable live models for generated explanations.':'AI can make mistakes. Use the source references to check important claims.'}</small></div></section>
      <aside className="studio-panel"><div className="section-heading"><h2>Learning studio</h2><Sparkles size={17}/></div><p className="muted">Turn understanding into practice.</p><button className="studio-card quiz-card" disabled={!ready} onClick={()=>{setPanel('quiz');setTopic('');}}><div className="card-icon"><Mic size={22}/></div><span className="eyebrow">SAY IT IN YOUR OWN WORDS</span><h3>Interview practice</h3><p>Challenge your knowledge with source-based questions.</p><span className="card-action">Create a quiz <Plus size={17}/></span></button><button className="studio-card deck-card" disabled={!ready} onClick={()=>{setPanel('deck');setTopic('');}}><div className="card-icon"><Presentation size={22}/></div><span className="eyebrow">GIVE YOUR IDEAS A STAGE</span><h3>Study slides</h3><p>Make a PowerPoint deck from what you’re learning.</p><span className="card-action">Create a deck <Plus size={17}/></span></button><div className="studio-note"><BookOpen size={19}/><h3>Read. Ask. Practice.</h3><p>Learning sticks when you do something with it.</p></div></aside></div>}
    </div>
    {panel&&<div className="modal-backdrop"><section className="studio-modal" role="dialog" aria-modal="true" aria-label={panel==='quiz'?'Interview practice':'Study slides'}><div className="modal-heading"><h2>{panel==='quiz'?<><Mic size={23}/> Interview practice</>:<><Presentation size={23}/> Study slides</>}</h2><button onClick={()=>setPanel(null)} aria-label="Close studio"><X/></button></div>{error&&<div className="error" role="alert">{error}</div>}<p>Choose a focus, or leave it blank for the key ideas in your notebook.</p><div className="studio-input"><input placeholder="e.g. System design trade-offs" value={topic} onChange={e=>setTopic(e.target.value)} maxLength={500}/><button className="primary" onClick={()=>void studio()} disabled={studioBusy}>{studioBusy?<LoaderCircle className="spin" size={18}/>:<Sparkles size={18}/>} {studioBusy?'Creating…':'Generate'}</button></div>{demo&&<small className="demo-note">Demo: excerpt-based examples. Live mode generates tailored content.</small>}
      {panel==='quiz'&&quiz&&<div className="quiz-results">{quiz.questions.map((q,i)=><article key={i}><span className="eyebrow">QUESTION {i+1}</span><h3>{q.question}</h3><textarea aria-label={`Your answer to question ${i+1}`} placeholder="Try answering before revealing the rubric…" rows={3}/><button className="text-button" onClick={()=>setRevealed(v=>v.includes(i)?v.filter(n=>n!==i):[...v,i])}>{revealed.includes(i)?'Hide answer':'Reveal answer & rubric'}</button>{revealed.includes(i)&&<div className="answer"><p>{q.answer}</p><ul>{q.rubric.map(r=><li key={r}>{r}</li>)}</ul>{sourceButtons(q.citations.map(n=>quiz.sources[n-1]),q.citations)}</div>}</article>)}</div>}
      {panel==='deck'&&deck&&<div className="deck-results"><div className="deck-title"><h3>{deck.title}</h3><button className="primary" onClick={()=>void download()}><Download size={17}/> Download PPTX</button></div>{deck.slides.map((s,i)=><article key={i}><span>{String(i+1).padStart(2,'0')}</span><div><h3>{s.title}</h3><ul>{s.bullets.map(b=><li key={b}>{b}</li>)}</ul><small>Sources: {s.citations.map(n=>`[${n}]`).join(' ')}</small></div></article>)}</div>}
    </section></div>}
    {source&&<div className="modal-backdrop source-backdrop"><section className="source-modal" role="dialog" aria-modal="true" aria-label="Source excerpt"><div className="modal-heading"><h2><FileText size={20}/>{source.name}</h2><button onClick={()=>setSource(null)} aria-label="Close source"><X/></button></div><span className="eyebrow">PAGE {source.page} · {source.modality.toUpperCase()} EXCERPT</span><p className="excerpt">{source.text}</p><button className="text-button" onClick={()=>setSource(null)}><ArrowLeft size={15}/> Back to learning</button></section></div>}
  </div>;
}
