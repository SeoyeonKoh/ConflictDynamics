import type { Control, ServerMessage } from './messages';

export type Link = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'replay';

/** The engine stops a run at its token cap with a paused status and this message (llm.py). */
export const BUDGET_SPENT = /token budget reached/i;
/** The engine paused itself and exited (token cap, subscription limit, a model that would not
 *  load): its paused status carries the reason. A viewer's own pause carries no message. */
export const engineStopped = (m: { state: string; message: string }) => m.state === 'paused' && !!m.message;
/** A status after which the engine process is gone: no point reconnecting. */
export const isEnd = (m: { state: string; message: string }) =>
  m.state === 'completed' || m.state === 'failed' || engineStopped(m);

/** Keeps one socket open, reconnecting until the run reports a terminal status. */
export function connect(
  url: string,
  onMessage: (message: ServerMessage) => void,
  onLink: (link: Link) => void,
): (control: Control) => void {
  let socket: WebSocket;
  let finished = false;
  const open = () => {
    onLink('connecting');
    socket = new WebSocket(url);
    socket.onopen = () => onLink('open');
    socket.onmessage = e => {
      const message = JSON.parse(e.data) as ServerMessage;
      if (message.type === 'status') finished = isEnd(message);
      onMessage(message);
    };
    socket.onclose = () => {
      onLink(finished ? 'closed' : 'reconnecting');
      if (!finished) setTimeout(open, 1000);
    };
  };
  open();
  return control => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(control));
  };
}
