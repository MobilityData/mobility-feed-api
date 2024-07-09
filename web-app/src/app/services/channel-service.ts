let channels: Map<string, BroadcastChannel> | undefined;

export const LOGOUT_CHANNEL = 'logout-channel';
export const LOGIN_CHANNEL = 'login-channel';

/**
 * Creates a new channel with the specified name and dispatcher. The dispatcher is called when a message is received.
 * If the channel already exists, the function returns false.
 * @param channelName name of the channel
 * @param dispatcher function to be called when a message is received
 * @returns true if the channel was created, false if the channel already exists
 * @see broadcastMessage
 */
export const createDispatchChannel = (
  channelName: string,
  dispatcher: () => void,
): boolean => {
  if (channels === undefined) {
    channels = new Map<string, BroadcastChannel>();
  }
  let channel = channels.get(channelName);
  if (channel !== undefined) {
    return false;
  }
  channel = new BroadcastChannel(channelName);
  channel.onmessage = () => {
    dispatcher();
  };
  channels.set(channelName, channel);
  return true;
};

/**
 * Broadcasts a message to all subscribers of the channel. The channel must be created before broadcasting.
 * If the channel is not found, an error is thrown.
 * @param channelName name of the channel
 * @param message to be broadcasted or undefined
 * @see createDispatchChannel
 */
export const broadcastMessage = (
  channelName: string,
  message?: string,
): void => {
  if (channels === undefined) {
    throw new Error('No channels created');
  }
  const channel = channels.get(channelName);
  if (channel === undefined) {
    throw new Error(`Channel ${channelName} not found`);
  }
  channel.postMessage(message);
};
