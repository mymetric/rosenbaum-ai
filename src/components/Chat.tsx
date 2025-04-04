import { useState } from 'react';
import { useSession } from 'next-auth/react';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  createdAt: string;
  userId: string;
}

export default function Chat() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');

  const sendMessage = async (message: string) => {
    if (!message.trim() || !session?.user?.email) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      content: message,
      role: 'user',
      createdAt: new Date().toISOString(),
  const newMessage: Message = {
    id: Date.now().toString(),
    content: message,
    role: 'user',
    createdAt: new Date().toISOString(),
    userId: session.user.email
  };

  setMessages(prev => [...prev, newMessage]);
  setInputValue('');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        userId: session.user.email
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const data = await response.json();
    
    // Add the assistant's response to messages
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      content: data.message,
      role: 'assistant',
      createdAt: new Date().toISOString(),
      userId: session.user.email
    };
    
    setMessages(prev => [...prev, assistantMessage]);

    // Clear the cache after successful response
    await fetch('/api/chat/clear-cache', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        userId: session.user.email
      }),
    });
  } catch (error) {
    console.error('Error sending message:', error);
    // Remove the user message from messages if there was an error
    setMessages(prev => prev.filter(msg => msg.id !== newMessage.id));
  }
}; 