export type Source = {id:string; document:string; name:string; page:number; text:string; modality:string; score:number};

export class ApiError extends Error {
  status:number;
  constructor(message:string,status:number) {super(message);this.name='ApiError';this.status=status;}
}
export const isGatewayError=(status:number)=>[502,503,504].includes(status);

export function waitForRetry(ms:number,signal?:AbortSignal|null):Promise<void> {
  return new Promise((resolve,reject)=>{
    const aborted=()=>{clearTimeout(timer);signal?.removeEventListener('abort',aborted);reject(signal?.reason??new DOMException('Aborted','AbortError'));};
    const timer=setTimeout(()=>{signal?.removeEventListener('abort',aborted);resolve();},ms);
    if(signal?.aborted){aborted();return;}
    signal?.addEventListener('abort',aborted,{once:true});
  });
}

async function gatewayFetch(path:string,options:RequestInit,retry:boolean):Promise<Response> {
  for(let attempt=0;;attempt++) {
    const response=await fetch('/api'+path,options);
    // Retry only rejected gateway responses before consuming any SSE data.
    // Never replay a chat stream after it has started, or retry other POST operations.
    if(!retry||!isGatewayError(response.status)||attempt>=3)return response;
    await response.body?.cancel();
    await waitForRetry(1000*2**attempt,options.signal);
  }
}

export async function request<T>(path:string,token:string,options:RequestInit={}):Promise<T> {
  const response=await gatewayFetch(path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),Authorization:'Bearer '+token,...options.headers}},(options.method??'GET').toUpperCase()==='GET');
  if(!response.ok) {
    const fallback=response.status===413?'Upload too large. Maximum file size is 20 MB.':isGatewayError(response.status)?'The API is restarting or unavailable. Please try again shortly.':`Request failed (${response.status})`;
    const error=await response.json().catch(()=>({detail:fallback}));
    throw new ApiError(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail),response.status);
  }
  return response.json();
}
export async function stream(path:string,token:string,options:RequestInit,onEvent:(event:Record<string,unknown>)=>void) {
  const response=await gatewayFetch(path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},signal:options.signal},true);
  if(!response.ok) throw new ApiError(isGatewayError(response.status)?'The API is restarting or unavailable. Please try again shortly.':`Request failed (${response.status})`,response.status);
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
