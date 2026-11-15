/**
 * Écran Tribunal (annexe D.6), précédé du chargement qui déroule la trace (D.5).
 * Bilan du Greffier, débat Procureur / Avocat, trace, pièces, contre-interrogatoire.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Argument, DecisionUI, Piece, Profil, ResultatTribunal } from '../api/types';
import { MODE_DIRECT, ProcesNonEnregistre, jugerDecision } from '../api/tribunal';
import { Gabarit, useTitre } from '../components/Gabarit';
import { Bouton } from '../components/Bouton';
import { IconeStatut, PastillePiece, Provenance, Statut } from '../components/Etiquettes';
import { LienRetour, Message } from '../components/Elements';
import { Icone } from '../components/Icone';
import { TiroirPiece } from '../components/TiroirPiece';
import { TrompezLeGreffier } from '../components/TrompezLeGreffier';
import { date } from '../lib/format';
import { libelleDecision } from '../domaine/decision';
import { questionsSuggerees, repondre, type QuestionSuggeree } from '../domaine/questions';
import { useEtatProfil } from '../state/store';
import { useTables } from '../state/useTables';
import styles from './Tribunal.module.css';

const DUREE_ETAPE_MS = 300;
const PHASES = ['Agent Profil : lecture de la demande', 'Orchestrateur : choix des pièces', 'Procureur et Avocat : plaidoiries', 'Greffier : contrôle des chiffres et du Pacte'];

function mouvementReduit(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

function Chargement({ resultat, etapesVisibles, debut }: { resultat?: ResultatTribunal; etapesVisibles: number; debut: number }) {
  const [secondes, setSecondes] = useState(0);
  useEffect(() => {
    if (resultat) return undefined;
    const minuterie = setInterval(() => setSecondes(Math.round((Date.now() - debut) / 1000)), 1000);
    return () => clearInterval(minuterie);
  }, [resultat, debut]);
  return (
    <section className={styles.chargement} aria-labelledby="titre-chargement" aria-busy={!resultat}>
      <h1 className="t-h1" id="titre-chargement">Le Tribunal instruit le dossier</h1>
      <p className="t-citation c-700">
        {resultat ? 'Instruction terminée : voici les étapes tracées.' : `Les agents rassemblent les pièces et plaident. Un procès dure souvent 20 à 40 secondes${secondes ? ` (${secondes} s)` : ''}.`}
      </p>
      <ol className={styles.chronologie} aria-live="polite">
        {resultat
          ? resultat.trace.slice(0, etapesVisibles).map((e, i) => (
            <li key={i} className={styles.etapeChrono}>
              <span className={`${styles.pastilleChrono} ${e.etat === 'signalement' ? styles.pastilleSignalement : ''}`} aria-hidden="true">
                <Icone nom={e.etat === 'signalement' ? 'alerte' : 'check'} taille={14} />
              </span>
              <span className="t-petit-fort">{e.role}</span>
              <code className="t-trace c-700">{e.appel}</code>
            </li>
          ))
          : PHASES.map((p) => (
            <li key={p} className={`${styles.etapeChrono} ${styles.enCours}`}>
              <span className={styles.pastilleChrono} aria-hidden="true" />
              <span className="t-petit c-700">{p}</span>
            </li>
          ))}
      </ol>
    </section>
  );
}

function CarteArgument({ argument, numero, surligne, onOuvrir }: { argument: Argument; numero: number; surligne: boolean; onOuvrir: (code: string, el: HTMLElement) => void }) {
  return (
    <li className={`${styles.argument} ${surligne ? styles.argumentSurligne : ''}`}>
      <p className="t-corps">
        <span className="visuellement-cache">{argument.camp}, argument {numero} : </span>
        {argument.texte}
      </p>
      <p className={styles.provenanceArgument}>
        <Provenance type={argument.provenance} />
        {argument.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={onOuvrir} />)}
      </p>
    </li>
  );
}

function Camp({ camp, args, surlignes, onOuvrir, limite }: {
  camp: 'Procureur' | 'Avocat';
  args: Argument[];
  surlignes: Set<string>;
  onOuvrir: (code: string, el: HTMLElement) => void;
  limite?: string;
}) {
  const [tout, setTout] = useState(false);
  const visibles = tout ? args : args.slice(0, 3);
  const id = `camp-${camp}`;
  return (
    <section className={`${styles.camp} ${camp === 'Procureur' ? styles.procureur : styles.avocat}`} aria-labelledby={id}>
      <div className={styles.enteteCamp}>
        <h2 className="t-panneau" id={id}>{camp}</h2>
        <p className="t-petit c-700">{camp === 'Procureur' ? 'contre la décision' : 'pour la décision'}</p>
      </div>
      <ol className={styles.arguments}>
        {visibles.map((a, i) => (
          <CarteArgument key={a.texte} argument={a} numero={i + 1} surligne={surlignes.has(`${camp}-${i + 1}`)} onOuvrir={onOuvrir} />
        ))}
      </ol>
      {args.length > 3 && (
        <Bouton variante="tertiaire" compact fleche={false} aria-expanded={tout} onClick={() => setTout((t) => !t)}>
          {tout ? 'Réduire' : `Voir ${args.length - 3} autre${args.length - 3 > 1 ? 's' : ''} argument${args.length - 3 > 1 ? 's' : ''}`}
        </Bouton>
      )}
      {limite && (
        <p className={styles.limite}>
          <Icone nom="alerte" taille={16} />
          <span className="t-petit">{limite}</span>
        </p>
      )}
    </section>
  );
}

function Repli({ titre, sousTitre, children, id }: { titre: string; sousTitre: string; children: React.ReactNode; id: string }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <div className={styles.repli}>
      <h2 className={styles.titreRepli}>
        <button type="button" aria-expanded={ouvert} aria-controls={id} onClick={() => setOuvert((o) => !o)} className={styles.boutonRepli}>
          <span className={styles.texteRepli}>
            <span className="t-intertitre">{titre}</span>
            <span className="t-petit c-500">{sousTitre}</span>
          </span>
          <Icone nom={ouvert ? 'chevron-haut' : 'chevron-bas'} taille={20} />
        </button>
      </h2>
      <div id={id} hidden={!ouvert} className={styles.contenuRepli}>{children}</div>
    </div>
  );
}

function NonEnregistre({ profil, decision, enregistree, onRejouer }: { profil: Profil; decision: DecisionUI; enregistree: DecisionUI | null; onRejouer: () => void }) {
  return (
    <div className={styles.corps}>
      <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
      <Message type="À vérifier" titre={`Aucun procès enregistré pour « ${libelleDecision(decision)} »`}>
        <p>
          En mode démonstration, Astrée rejoue des procès réellement tenus par les agents Bedrock, sans rien inventer.
          Pour juger cette décision, il faut le Tribunal en direct (VITE_USE_MOCKS=false et l'adresse de la Lambda).
        </p>
      </Message>
      <div className={styles.actions}>
        <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/decision`}>Retour à la décision</Bouton>
        {enregistree && (
          <Bouton variante="primaire" onClick={onRejouer}>Voir le procès de « {libelleDecision(enregistree)} »</Bouton>
        )}
      </div>
    </div>
  );
}

export function Tribunal({ profil }: { profil: Profil }) {
  useTitre('Tribunal');
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { etat, definirTribunal, definirDecision, ajouterReponse } = useEtatProfil(profil.id);
  const { decision, tribunal } = etat;
  const { tablePosition } = useTables(profil.id, decision);
  const [animer, setAnimer] = useState(false);
  const [etapesVisibles, setEtapesVisibles] = useState(0);
  const [debut] = useState(Date.now());
  const [question, setQuestion] = useState('');
  const [noteQuestion, setNoteQuestion] = useState(false);
  const [controlesOuverts, setControlesOuverts] = useState(false);
  const declencheur = useRef<HTMLElement | null>(null);
  const resultat = tribunal.resultat;

  const lancer = useCallback(() => {
    if (!decision) return;
    setAnimer(true);
    setEtapesVisibles(0);
    definirTribunal({ statut: 'chargement' });
    jugerDecision(profil.id, decision)
      .then((r) => definirTribunal({ statut: 'pret', resultat: r }))
      .catch((e: unknown) => {
        if (e instanceof ProcesNonEnregistre) definirTribunal({ statut: 'non_enregistre', decisionEnregistree: e.decisionEnregistree });
        else definirTribunal({ statut: 'erreur', erreur: e instanceof Error ? e.message : String(e) });
      });
  }, [decision, definirTribunal, profil.id]);

  // Un seul procès par décision : en mode direct, chaque appel coûte des appels Bedrock.
  // (Le mode strict de React exécute les effets deux fois en développement.)
  const dejaLance = useRef<string | null>(null);
  useEffect(() => {
    const signature = JSON.stringify(decision);
    if (decision && tribunal.statut === 'vide' && dejaLance.current !== signature) {
      dejaLance.current = signature;
      lancer();
    }
  }, [decision, tribunal.statut, lancer]);

  useEffect(() => {
    if (!animer || !resultat) return undefined;
    if (mouvementReduit()) {
      setEtapesVisibles(resultat.trace.length);
      setAnimer(false);
      return undefined;
    }
    if (etapesVisibles >= resultat.trace.length) {
      const fin = setTimeout(() => setAnimer(false), DUREE_ETAPE_MS * 2);
      return () => clearTimeout(fin);
    }
    const suivante = setTimeout(() => setEtapesVisibles((n) => n + 1), DUREE_ETAPE_MS);
    return () => clearTimeout(suivante);
  }, [animer, resultat, etapesVisibles]);

  const pieces: Piece[] = useMemo(() => [...(resultat?.pieces ?? []), ...etat.piecesQuestions], [resultat, etat.piecesQuestions]);
  const codePiece = params.get('piece');
  const pieceOuverte = codePiece ? pieces.find((p) => p.code === codePiece) : undefined;

  const ouvrirPiece = useCallback((code: string, el: HTMLElement) => {
    declencheur.current = el;
    params.set('piece', code);
    setParams(params);
  }, [params, setParams]);
  const fermerPiece = useCallback(() => {
    params.delete('piece');
    setParams(params);
  }, [params, setParams]);

  // Le focus revient au déclencheur une fois le tiroir fermé et la page redevenue active (annexe D.6).
  const tiroirOuvert = Boolean(pieceOuverte);
  const etaitOuvert = useRef(false);
  useEffect(() => {
    if (etaitOuvert.current && !tiroirOuvert) declencheur.current?.focus();
    etaitOuvert.current = tiroirOuvert;
  }, [tiroirOuvert]);

  if (!decision) {
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal">
        <div className={styles.corps}>
          <Message type="À vérifier" titre="Aucune décision à juger">
            <p>Choisissez d'abord un titre ou composez un panier depuis votre portefeuille.</p>
          </Message>
          <Bouton variante="secondaire" vers={`/${profil.id}/portefeuille`}>Aller au portefeuille</Bouton>
        </div>
      </Gabarit>
    );
  }

  if (tribunal.statut === 'non_enregistre') {
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal">
        <NonEnregistre
          profil={profil}
          decision={decision}
          enregistree={tribunal.decisionEnregistree ?? null}
          onRejouer={() => tribunal.decisionEnregistree && definirDecision(tribunal.decisionEnregistree)}
        />
      </Gabarit>
    );
  }

  if (tribunal.statut === 'erreur') {
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal">
        <div className={styles.corps}>
          <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
          <Message type="Violation" titre="Le procès n'a pas pu aller au bout" correction={{ libelle: 'Réessayer', onClick: lancer }}>
            <p>{tribunal.erreur}</p>
            <p className="t-petit c-700">Votre décision « {libelleDecision(decision)} » est conservée.</p>
          </Message>
        </div>
      </Gabarit>
    );
  }

  if (!resultat || animer) {
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal">
        <div className={styles.corps}>
          <Chargement resultat={resultat} etapesVisibles={etapesVisibles} debut={debut} />
        </div>
      </Gabarit>
    );
  }

  const procureur = resultat.arguments.filter((a) => a.camp === 'Procureur');
  const avocat = resultat.arguments.filter((a) => a.camp === 'Avocat');
  const surlignes = new Set<string>();
  if (pieceOuverte) {
    procureur.forEach((a, i) => a.pieces.includes(pieceOuverte.code) && surlignes.add(`Procureur-${i + 1}`));
    avocat.forEach((a, i) => a.pieces.includes(pieceOuverte.code) && surlignes.add(`Avocat-${i + 1}`));
  }
  const comptes = (['Violation', 'À vérifier', 'Conforme'] as const).map((s) => ({ statut: s, n: resultat.controles.filter((c) => c.statut === s).length }));
  const manquantes = resultat.controles.filter((c) => /source manquante/i.test(c.texte)).length;
  const principal = resultat.controles.find((c) => c.paragraphe !== undefined && c.statut === 'Violation');
  const reglePrincipale = principal && resultat.contrat.pacte.regles.find((r) => r.id === principal.regle);
  const contexteQuestions = { profil, resultat, decision, table: tablePosition, pieces };
  const questions = questionsSuggerees(contexteQuestions);
  const dejaPosees = new Set(etat.reponses.map((r) => r.question));

  const poser = (q: QuestionSuggeree) => {
    const reponse = repondre(q, contexteQuestions);
    if (reponse) ajouterReponse(reponse);
  };
  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    const correspondante = questions.find((q) => q.libelle.toLowerCase() === question.trim().toLowerCase());
    if (correspondante) poser(correspondante);
    else setNoteQuestion(true);
    setQuestion('');
  };

  return (
    <>
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal" inerte={Boolean(pieceOuverte)}>
        <div className={styles.corpsLarge}>
          <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
          <div className={styles.titre}>
            <p className="t-etiquette c-500">
              Audience n° {resultat.audience} · instruction terminée
              {manquantes ? ` · ${manquantes} donnée${manquantes > 1 ? 's' : ''} manquante${manquantes > 1 ? 's' : ''}` : ''}
              {MODE_DIRECT ? '' : ' · procès enregistré'}
            </p>
            <h1 className="t-h1">{resultat.titre}</h1>
            <p className="t-citation c-700">Le Tribunal présente les deux côtés. C'est vous qui rendez le verdict.</p>
          </div>

          <section className={styles.bilan} aria-labelledby="titre-bilan">
            <div className={styles.resume}>
              <div className={styles.comptes}>
                <h2 className="t-intertitre" id="titre-bilan">Bilan du Greffier</h2>
                {comptes.map(({ statut, n }) => (
                  <span key={statut} className={styles.compte}>
                    <span className={`t-tableau-fort ${n ? '' : 'c-500'}`}>{n}</span>
                    <Statut type={statut} attenue={!n} />
                  </span>
                ))}
              </div>
              <p className="t-corps">{resultat.constat}</p>
              {reglePrincipale && (
                <p className="t-petit c-700">
                  Règle que vous avez signée le {date(resultat.contrat.pacte.date_signature)} (Pacte §{principal!.paragraphe}) :
                  « {reglePrincipale.libelle} ».
                </p>
              )}
            </div>
            <button type="button" className={styles.voirControles} aria-expanded={controlesOuverts} aria-controls="liste-controles" onClick={() => setControlesOuverts((o) => !o)}>
              {controlesOuverts ? 'Masquer les contrôles' : `Voir les ${resultat.controles.length} contrôles`}
              <Icone nom={controlesOuverts ? 'chevron-haut' : 'chevron-bas'} taille={14} />
            </button>
            <ol id="liste-controles" className={styles.controles} hidden={!controlesOuverts}>
              {resultat.controles.map((c) => (
                <li key={`${c.regle}-${c.texte}`} className={styles.controle}>
                  <Statut type={c.statut} />
                  <span className="t-petit">{c.texte}</span>
                  <span className={styles.piecesControle}>
                    {c.pieces.map((p) => <PastillePiece key={p} code={p} onOuvrir={ouvrirPiece} />)}
                  </span>
                </li>
              ))}
            </ol>
          </section>

          <div className={styles.debat}>
            <Camp camp="Procureur" args={procureur} surlignes={surlignes} onOuvrir={ouvrirPiece} />
            <Camp camp="Avocat" args={avocat} surlignes={surlignes} onOuvrir={ouvrirPiece} limite={resultat.limiteAvocat} />
          </div>

          {(resultat.argumentsRejetes.length > 0 || resultat.corrections.length > 0) && (
            <section className={styles.rejetes} aria-labelledby="titre-rejetes">
              <h2 className="t-intertitre" id="titre-rejetes">Arguments contrôlés par le Greffier pendant ce procès</h2>
              {resultat.corrections.length > 0 && (
                <p className="t-petit c-700">
                  Cas réel : l'agent a écrit un chiffre absent de ses pièces. Le Greffier l'a renvoyé une fois avec le motif
                  exact ; seule la version corrigée, qui a passé la vérification, est affichée dans le débat.
                </p>
              )}
              {resultat.corrections.map((c) => (
                <div key={c.original} className={styles.correction}>
                  <p className="t-petit-fort">{c.camp} · version renvoyée</p>
                  <p className={`t-petit ${styles.versionRenvoyee}`}>« {c.original} »</p>
                  <p className={styles.motifCorrection}>
                    <IconeStatut type="Violation" taille={14} />
                    <span className="t-petit-fort">Motif du Greffier : {c.motif}</span>
                  </p>
                  <p className="t-petit-fort">Version corrigée, acceptée</p>
                  <p className="t-petit">« {c.corrige} »</p>
                </div>
              ))}
              {resultat.argumentsRejetes.map((a) => (
                <p key={a.texte} className={styles.rejete}>
                  <IconeStatut type="Violation" taille={14} />
                  <span className="t-petit"><strong>{a.camp}</strong> · « {a.texte} » — écarté : {a.raison}</span>
                </p>
              ))}
            </section>
          )}

          <TrompezLeGreffier resultat={resultat} pieces={pieces} />

          <div className={styles.replis}>
            <Repli id="repli-trace" titre="Comment le Tribunal a travaillé" sousTitre={`${resultat.trace.length} étapes tracées : profil, outils choisis par l'orchestrateur, plaidoiries, contrôle`}>
              <ol className={styles.chronologie}>
                {resultat.trace.map((e, i) => (
                  <li key={i} className={styles.etapeChrono}>
                    <span className={`${styles.pastilleChrono} ${e.etat === 'signalement' ? styles.pastilleSignalement : ''}`} aria-hidden="true">
                      <Icone nom={e.etat === 'signalement' ? 'alerte' : 'check'} taille={14} />
                    </span>
                    <span className={styles.texteChrono}>
                      <span className="t-petit-fort">{e.role}{e.etat === 'signalement' && <span className="visuellement-cache"> (signalement)</span>}</span>
                      <code className="t-trace c-700">{e.appel}</code>
                      {e.raison && <span className="t-petit c-700">Raison : {e.raison}</span>}
                    </span>
                    {e.sortie && <PastillePiece code={e.sortie} onOuvrir={ouvrirPiece} />}
                  </li>
                ))}
              </ol>
            </Repli>
            <Repli id="repli-pieces" titre="Pièces à conviction" sousTitre={`${pieces.length} pièces : source, traitement et limites de chaque chiffre`}>
              <ul className={styles.listePieces}>
                {pieces.map((p) => (
                  <li key={p.code} className={styles.lignePiece}>
                    <PastillePiece code={p.code} onOuvrir={ouvrirPiece} />
                    <Provenance type={p.provenance} />
                    <span className="t-corps">{p.titre}</span>
                    <span className="t-tableau c-700">{p.valeur}</span>
                  </li>
                ))}
              </ul>
            </Repli>
          </div>

          <section className={styles.questions} aria-labelledby="titre-questions">
            <h2 className="t-intertitre" id="titre-questions">Une question pour les agents ?</h2>
            <div className={styles.suggestions}>
              {questions.map((q) => (
                <button key={q.id} type="button" className={styles.suggestion} disabled={dejaPosees.has(q.libelle)} onClick={() => poser(q)}>
                  {q.libelle}
                </button>
              ))}
            </div>
            <form className={styles.saisie} onSubmit={envoyer}>
              <label htmlFor="question-libre" className="visuellement-cache">Votre question aux agents</label>
              <input
                id="question-libre"
                className={styles.champQuestion}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Posez votre question : les agents répondent avec les pièces du dossier"
              />
              <Bouton variante="secondaire" fleche={false} type="submit">Envoyer</Bouton>
            </form>
            {noteQuestion && (
              <p className="t-petit c-700" role="status">
                Les questions libres passeront par l'orchestrateur Bedrock, qui choisira ses outils et ajoutera des pièces au dossier.
                Le pipeline sait déjà y répondre (route /question, #55), mais l'interface ne l'appelle pas encore : les questions suggérées ci-dessus sont calculées par le Greffier.
              </p>
            )}
            {etat.reponses.length > 0 && (
              <ol className={styles.reponses} aria-live="polite">
                {etat.reponses.map((r) => (
                  <li key={r.question} className={styles.reponse}>
                    <p className="t-petit-fort c-500">{r.question}</p>
                    <p className={styles.provenanceArgument}>
                      <span className="t-petit-fort">{r.role}</span>
                      <Provenance type={r.provenance} />
                      {r.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={ouvrirPiece} />)}
                    </p>
                    <p className="t-corps">{r.texte}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <div className={styles.actions}>
            <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/decision`}>Retour à la décision</Bouton>
            <Bouton variante="primaire" onClick={() => navigate(`/${profil.id}/verdict`)}>Rendre mon verdict</Bouton>
          </div>
        </div>
      </Gabarit>
      {pieceOuverte && createPortal(<TiroirPiece piece={pieceOuverte} onFermer={fermerPiece} />, document.body)}
    </>
  );
}
