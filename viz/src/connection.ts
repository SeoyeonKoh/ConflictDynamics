import type { Control, ServerMessage } from './messages';

export type Link = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'replay';

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
      if (message.type === 'status') finished = ['completed', 'failed'].includes(message.state);
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
