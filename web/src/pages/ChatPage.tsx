// Chat & Evidence — the pics/ mockup (mobile chat_page.dart): before the
// first question the ask bar sits under the title with the persona's
// Suggested Questions below it; once a conversation starts it becomes a
// transcript (every answer through AskAnswer with its evidence detail on)
// with the ask bar docked at the bottom. Questions handed over by other
// pages (useChat().askInChat) land here. Session-only: nothing persisted.
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AskAnswer from '../components/AskAnswer';
import { CityHintRow } from '../components/CityPicker';
import PageFrame from '../components/PageFrame';
import { ActionRow, Icon, InfoBanner, PageHeader, RuleLabel, SectionTitle, Spinner } from '../components/ui';
import { question, questionTitle } from '../data/personas';
import { useChat, type ChatTurn } from '../state/ChatContext';
import { useUiPrefs } from '../state/UiPrefsContext';

function Composer() {
  const { ask, loading } = useChat();
  const { personaInfo } = useUiPrefs();
  const [text, setText] = useState('');
  return (
    <form
      className="flex flex-col gap-space-xs"
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim() || loading) return;
        ask(text);
        setText('');
      }}
    >
      <div className="flex items-center gap-space-sm p-1.5 pl-3 rounded-card bg-card border border-card-border shadow-card focus-within:border-primary">
        <Icon name="chat_bubble" size={20} className="text-primary" />
        <input
          className="flex-1 min-w-0 bg-transparent border-0 outline-none font-body-md text-body-md text-ink placeholder:text-outline py-2"
          onChange={(e) => setText(e.target.value)}
          placeholder={personaInfo.askHint}
          aria-label="Ask a question"
          type="text"
          value={text}
        />
        <button
          className="shrink-0 w-10 h-10 rounded-xl bg-accent-gradient text-on-primary flex items-center justify-center shadow-md disabled:opacity-60 disabled:cursor-not-allowed"
          disabled={loading || text.trim() === ''}
          aria-label="Send"
          title="Send"
          type="submit"
        >
          {loading ? (
            <Spinner className="w-5 h-5 border-on-primary/40 border-t-on-primary" />
          ) : (
            <Icon name="send" size={20} fill />
          )}
        </button>
      </div>
      <CityHintRow />
    </form>
  );
}

/** The question bubble: the persona's accent gradient, square bottom-right. */
function UserBubble({ turn }: { turn: ChatTurn }) {
  return (
    <div className="flex justify-end pl-12">
      <div className="bg-accent-gradient text-on-primary p-space-md rounded-2xl rounded-br-none shadow-md max-w-2xl flex flex-col items-end gap-1.5">
        <span className="font-citation-mono text-citation-mono text-primary-fixed">
          {turn.askedAt} · {turn.lang.toUpperCase()}
        </span>
        <p className="font-body-lg text-body-lg font-medium">{turn.question}</p>
      </div>
    </div>
  );
}

/** The answer card: square bottom-left corner. */
function AnswerBubble({ turn }: { turn: ChatTurn }) {
  return (
    <div className="mr-space-sm p-3 bg-card border border-card-border shadow-card rounded-2xl rounded-bl-none">
      <AskAnswer
        asked={null}
        loading={!turn.outcome && !turn.error}
        outcome={turn.outcome}
        error={turn.error}
        detail
      />
    </div>
  );
}

export default function ChatPage() {
  const { turns, ask } = useChat();
  const { personaInfo: persona, cityInfo } = useUiPrefs();
  const end = useRef<HTMLDivElement>(null);
  const city = cityInfo.name;
  const navigate = useNavigate();

  // Keep the newest turn in view.
  useEffect(() => {
    if (turns.length > 0) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  if (turns.length === 0) {
    return (
      <PageFrame>
        <PageHeader title="Chat & Evidence" subtitle={persona.chatLead} />
        <div className="mt-space-lg">
          <Composer />
        </div>
        <div className="mt-space-md">
          <InfoBanner
            icon="schedule"
            title="When's the best time to go outside?"
            body="Find the best window today or tomorrow, and compare two times."
            onClick={() => navigate('/best-window')}
          />
        </div>
        <div className="mt-space-lg mb-space-sm">
          <SectionTitle text="Suggested Questions" />
        </div>
        <div className="flex flex-col gap-space-sm">
          {persona.suggestions.map((q) => (
            <ActionRow key={q.template} icon={q.icon} title={questionTitle(q, city)} onClick={() => ask(question(q, city))} />
          ))}
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame
      footer="none"
      dock={
        <div className="sticky bottom-16 lg:bottom-0 z-20 bg-sheet/95 backdrop-blur border-t border-card-border">
          <div className="mx-auto w-full max-w-3xl px-4 py-space-sm">
            <Composer />
          </div>
        </div>
      }
    >
      <h1 className="font-headline-md text-headline-md font-bold text-ink">Chat & Evidence</h1>
      <div className="mt-space-sm mb-space-md">
        <RuleLabel icon="bolt" text="Live — answers come from /ask" />
      </div>
      <div className="flex flex-col gap-space-sm">
        {turns.map((turn) => (
          <div key={turn.id} className="flex flex-col gap-space-sm mb-space-md">
            <UserBubble turn={turn} />
            <AnswerBubble turn={turn} />
          </div>
        ))}
      </div>
      <div ref={end} />
    </PageFrame>
  );
}
