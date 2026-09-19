// Edycja wiadomości przed wysłaniem (nowa, odpowiedź, szkic przygotowany przez Nexusa).
//
// Wysyłka zawsze wymaga kliknięcia „Wyślij” i potwierdzenia adresatów w tym oknie.

import { useState } from "react";
import { describe } from "../_biuro/http";
import { SendMailIcon } from "../_biuro/icons";
import { buttonClass, ErrorBanner, Field, inputClass, Modal, useConfirm } from "../_biuro/ui";
import { mailApi, parseAddresses, type DraftPayload, type PendingMail } from "./api";

export function ComposeDialog({
  initial,
  pending,
  onClose,
  onDone,
}: {
  initial: DraftPayload;
  /** Istniejąca oczekująca wiadomość (np. od Nexusa) – zmiany zapisywane są w niej. */
  pending?: PendingMail;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [to, setTo] = useState(initial.to.join(", "));
  const [cc, setCc] = useState(initial.cc.join(", "));
  const [bcc, setBcc] = useState(initial.bcc.join(", "));
  const [showCopies, setShowCopies] = useState(initial.cc.length > 0 || initial.bcc.length > 0);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const [error, setError] = useState(pending?.error ?? "");
  const [busy, setBusy] = useState<"" | "send" | "save" | "draft">("");
  const [confirm, confirmDialog] = useConfirm();

  const draft = (): DraftPayload => ({
    ...initial,
    to: parseAddresses(to),
    cc: parseAddresses(cc),
    bcc: parseAddresses(bcc),
    subject: subject.trim(),
    body,
  });

  /** Zapisuje treść jako oczekującą wiadomość (nową albo istniejącą) i zwraca jej identyfikator. */
  const store = async (): Promise<string> => {
    const value = draft();
    if (pending) {
      const { reply: _reply, in_reply_to: _inReplyTo, references: _references, ...changes } = value;
      await mailApi.updatePending(pending.id, changes);
      return pending.id;
    }
    return (await mailApi.createPending(value)).id;
  };

  const act = async (kind: "send" | "save" | "draft") => {
    setError("");
    const value = draft();
    if (kind === "send") {
      if (!value.to.length) {
        setError("Podaj adresata.");
        return;
      }
      const recipients = [...value.to, ...value.cc, ...value.bcc];
      const ok = await confirm({
        title: "Wysłać wiadomość?",
        message: (
          <>
            Wiadomość <strong>„{value.subject || "(bez tematu)"}”</strong> zostanie wysłana do:{" "}
            <strong>{recipients.join(", ")}</strong>.
          </>
        ),
        confirmLabel: "Wyślij",
      });
      if (!ok) return;
    }
    setBusy(kind);
    try {
      const id = await store();
      if (kind === "send") {
        await mailApi.send(id);
        onDone("Wiadomość wysłana");
      } else if (kind === "draft") {
        const result = await mailApi.saveDraft(id);
        onDone(`Zapisano w folderze ${result.folder}`);
      } else {
        onDone("Zapisano w oczekujących");
      }
      onClose();
    } catch (failure) {
      setError(describe(failure));
      setBusy("");
    }
  };

  return (
    <>
    <Modal
      title={pending ? "Wiadomość do zatwierdzenia" : initial.reply ? "Odpowiedź" : "Nowa wiadomość"}
      onClose={onClose}
      wide
      footer={
        <>
          <button type="button" className={`${buttonClass.ghost} mr-auto`} disabled={busy !== ""} onClick={() => act("draft")}>
            {busy === "draft" && <span className="spinner" />} Zapisz w Szkicach
          </button>
          <button type="button" className={buttonClass.secondary} disabled={busy !== ""} onClick={() => act("save")}>
            {busy === "save" && <span className="spinner" />} Na później
          </button>
          <button type="button" className={buttonClass.primary} disabled={busy !== ""} onClick={() => act("send")}>
            {busy === "send" ? <span className="spinner" /> : <SendMailIcon size={17} />} Wyślij
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {pending && (
          <p className="rounded-xl bg-accent-soft/50 px-3 py-2 text-sm">
            Treść przygotował asystent. Sprawdź adresatów i treść – nic nie zostanie wysłane bez Twojego kliknięcia.
          </p>
        )}
        <Field label="Do">
          <input className={inputClass} value={to} onChange={(event) => setTo(event.target.value)} placeholder="adres@firma.pl, …" />
        </Field>
        {showCopies ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="DW (kopia)">
              <input className={inputClass} value={cc} onChange={(event) => setCc(event.target.value)} />
            </Field>
            <Field label="UDW (ukryta kopia)">
              <input className={inputClass} value={bcc} onChange={(event) => setBcc(event.target.value)} />
            </Field>
          </div>
        ) : (
          <button type="button" className="text-xs text-accent hover:underline" onClick={() => setShowCopies(true)}>
            Dodaj DW / UDW
          </button>
        )}
        <Field label="Temat">
          <input className={inputClass} value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={300} />
        </Field>
        <Field label="Treść">
          <textarea
            className={`${inputClass} min-h-64 resize-y font-sans leading-relaxed`}
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </Field>
        {(initial.file_ids?.length ?? 0) > 0 && (
          <p className="text-xs text-muted">Załączniki z rozmowy: {initial.file_ids?.length}</p>
        )}
        <ErrorBanner message={error} />
      </div>
    </Modal>
    {confirmDialog}
    </>
  );
}
