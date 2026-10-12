export type Source = {id:string; document:string; name:string; page:number; text:string; modality:string; score:number};
export async function request<T>(path:string,token:string,options:RequestInit={}):Promise<T> {
  const response=await fetch('/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),Authorization:'Bearer '+token,...options.headers}});
  if(!response.ok) {
    const error=await response.json().catch(()=>({detail:'Request failed'}));
    throw new Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail));
  }
  return response.json();
}
export async function stream(path:string,token:string,options:RequestInit,onEvent:(event:Record<string,unknown>)=>void) {
  const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},signal:options.signal});
  if(!response.ok) throw new Error(`Request failed (${response.status})`);
  if(!response.body) throw new Error('Streaming unavailable');
  const reader=response.body.getReader(),decoder=new TextDecoder();
  let buffer='';
  try {
    while(true) {
      const {done,value}=await reader.read();
      buffer+=decoder.decode(value,{stream:!done});
      let end:number;
      while((end=buffer.indexOf('\n\n'))!==-1) {
        const frame=buffer.slice(0,end); buffer=buffer.slice(end+2);
        const data=frame.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).join('\n');
        if(data) onEvent(JSON.parse(data));
      }
      if(done) break;
    }
  } finally {reader.releaseLock();}
}
