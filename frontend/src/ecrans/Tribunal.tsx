/**
 * Écran Tribunal (annexe D.6), précédé du chargement (D.5) qui montre la vraie progression du
 * procès en direct, ou la relecture d'un procès enregistré (#90).
 * Bilan du Greffier, débat Procureur / Avocat, trace, pièces, contre-interrogatoire.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Argument, DecisionUI, Piece, Profil, ProgressionTribunal, ResultatTribunal } from '../api/types';
import { MODE_DIRECT, ProcesNonEnregistre, jugerDecision, poserQuestion, questionLibreDisponible, reprendreProces, reveillerLambda } from '../api/tribunal';
import { adapterEchange } from '../api/adaptateur';
import { Gabarit, useTitre } from '../components/Gabarit';
import { Bouton } from '../components/Bouton';
import { ChargementTribunal, DossierInstruit, type PropsChargement } from '../components/ChargementTribunal';
import { IconeStatut, PastillePiece, Provenance, Statut } from '../components/Etiquettes';
import { LienRetour, Message } from '../components/Elements';
import { Icone } from '../components/Icone';
import { TiroirPiece } from '../components/TiroirPiece';
import { TrompezLeGreffier } from '../components/TrompezLeGreffier';
import { date } from '../lib/format';
import { libelleDecision } from '../domaine/decision';
import { resultatCalibrage } from '../domaine/calibrage';
import { phaseEnRelecture } from '../domaine/progression';
import { donneesCalibrage } from '../api/donnees';
import { questionsSuggerees, repondre, type QuestionSuggeree } from '../domaine/questions';
import { useEtatProfil } from '../state/store';
import { useTables } from '../state/useTables';
import styles from './Tribunal.module.css';

/** Relecture d'un procès enregistré : rythme fixe, annoncé à l'écran (#90). */
const DUREE_ETAPE_RELECTURE_MS = 500;
/** Toutes les phases cochées restent visibles un instant avant le résultat. */
const DUREE_FIN_MS = 800;

function mouvementReduit(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Première phrase d'un argument, pour la ligne repliée. Une phrase finit sur « . », « ! » ou « ? »
 * suivi d'une majuscule : « déc. 2021 » ou « −15,1 % » ne coupent pas.
 */
/** Espaces insécables dans « 188 291 $ » et « −29,0 % » : un montant n'est jamais coupé en fin de ligne. */
export function sansCoupure(texte: string): string {
  return texte.replace(/(\d) (?=\d{3}(?!\d))/g, '$1\u202f').replace(/(\d) (?=[$%])/g, '$1\u00a0');
}

export function accroche(texte: string): { tete: string; suite: string } {
  const fin = texte.search(/[.!?»](?=\s+[A-ZÀÂÉÈÊÎÔÛÇ«])/);
  if (fin < 0) return { tete: texte, suite: '' };
  return { tete: texte.slice(0, fin + 1), suite: texte.slice(fin + 1).trim() };
}

function CarteArgument({ argument, numero, surligne, ouvertAuDepart, onOuvrir }: {
  argument: Argument;
  numero: number;
  surligne: boolean;
  ouvertAuDepart: boolean;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const [ouvert, setOuvert] = useState(ouvertAuDepart);
  const deplie = ouvert || surligne;
  const { tete, suite } = accroche(sansCoupure(argument.texte));
  const id = `argument-${argument.camp}-${numero}`;
  return (
    <li className={`${styles.argument} ${deplie ? styles.argumentOuvert : ''} ${surligne ? styles.argumentSurligne : ''}`}>
      <button type="button" className={styles.teteArgument} aria-expanded={deplie} aria-controls={id} onClick={() => setOuvert((o) => !o)}>
        <span className={styles.numeroArgument} aria-hidden="true">{numero}</span>
        <span className={`t-corps ${styles.accroche}`}>
          <span className="visuellement-cache">{argument.camp}, argument {numero} : </span>
          {tete}
        </span>
        <Icone nom={deplie ? 'chevron-haut' : 'chevron-bas'} taille={16} />
      </button>
      <div id={id} hidden={!deplie} className={styles.corpsArgument}>
        {suite && <p className="t-corps c-700">{suite}</p>}
        <p className={styles.provenanceArgument}>
          <Provenance type={argument.provenance} />
          {argument.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={onOuvrir} />)}
        </p>
      </div>
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
  const id = `camp-${camp}`;
  return (
    <section className={`${styles.camp} ${camp === 'Procureur' ? styles.procureur : styles.avocat}`} aria-labelledby={id}>
      <div className={styles.enteteCamp}>
        <h2 className="t-panneau" id={id}>{camp}</h2>
        <p className="t-petit c-500">
          {camp === 'Procureur' ? 'contre la décision' : 'pour la décision'} · {args.length} argument{args.length > 1 ? 's' : ''}
        </p>
      </div>
      <ol className={styles.arguments}>
        {args.map((a, i) => (
          <CarteArgument key={a.texte} argument={a} numero={i + 1} ouvertAuDepart={i === 0}
            surligne={surlignes.has(`${camp}-${i + 1}`)} onOuvrir={onOuvrir} />
        ))}
      </ol>
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

function NonEnregistre({ profil, decision, enregistree, onRejouer, raisonPacteVecu }: { profil: Profil; decision: DecisionUI; enregistree: DecisionUI | null; onRejouer: () => void; raisonPacteVecu?: string }) {
  return (
    <div className={styles.corps}>
      <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
      <Message type="À vérifier" titre={`Aucun procès enregistré pour « ${libelleDecision(decision)} »`}>
        <p>
          En mode démonstration, Astrée rejoue des procès réellement tenus par les agents Bedrock, sans rien inventer.
          Pour juger cette décision, il faut le Tribunal en direct (VITE_USE_MOCKS=false et l'adresse de la Lambda).
        </p>
        {raisonPacteVecu && <p>{raisonPacteVecu}</p>}
      </Message>
      <div className={styles.actions}>
        <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/decision`}>Retour à la décision</Bouton>
        {raisonPacteVecu && (
          <Bouton variante="secondaire" vers={`/${profil.id}/pacte-vecu`}>Revoir mes réponses</Bouton>
        )}
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
  const { etat, definirTribunal, definirDecision, ajouterReponse, ajouterEchange } = useEtatProfil(profil.id);
  const { decision, tribunal } = etat;
  const { tablePosition } = useTables(profil, decision);
  const [animer, setAnimer] = useState(false);
  const [etapesVisibles, setEtapesVisibles] = useState(0);
  const [debut] = useState(Date.now());
  const [question, setQuestion] = useState('');
  const [noteQuestion, setNoteQuestion] = useState(false);
  const [questionEnCours, setQuestionEnCours] = useState<{ question: string; debut: number } | null>(null);
  const [secondesQuestion, setSecondesQuestion] = useState(0);
  const [erreurQuestion, setErreurQuestion] = useState<string | null>(null);
  const [controlesOuverts, setControlesOuverts] = useState(false);
  const declencheur = useRef<HTMLElement | null>(null);
  const resultat = tribunal.resultat;
  // Réponses du Pacte vécu (#68), seulement s'il est terminé : le Tribunal les recalcule en Python.
  const donnees = donneesCalibrage(profil.id);
  const reponsesCalibrage = etat.calibrage?.reponses;
  const reponsesPacteVecu = useMemo(
    () => (donnees && reponsesCalibrage && resultatCalibrage(donnees, reponsesCalibrage).complet ? reponsesCalibrage : null),
    [donnees, reponsesCalibrage],
  );

  // Progression réelle du procès en direct (#90), relue sur la Lambda pendant l'attente.
  const [progression, setProgression] = useState<ProgressionTribunal | null>(null);
  const suivi = useRef<AbortController | null>(null);

  /** Suit un procès (lancé ou repris) ; un suivi interrompu (écran quitté) ne touche plus à l'état. */
  const suivre = useCallback((proces: (signal: AbortSignal) => Promise<ResultatTribunal>, accepte: () => boolean) => {
    suivi.current?.abort();
    const controleur = new AbortController();
    suivi.current = controleur;
    proces(controleur.signal)
      .then((r) => {
        if (controleur.signal.aborted) return;
        if (MODE_DIRECT) setEtapesVisibles(r.trace.length); // déjà vues en direct : pas de relecture
        definirTribunal({ statut: 'pret', resultat: r });
      })
      .catch((e: unknown) => {
        if (controleur.signal.aborted) {
          // Écran quitté avant que la Lambda accepte le procès : on repartira de zéro en revenant.
          if (!accepte()) definirTribunal({ statut: 'vide' });
          return;
        }
        if (e instanceof ProcesNonEnregistre) {
          definirTribunal({ statut: 'non_enregistre', decisionEnregistree: e.decisionEnregistree, erreur: e.raisonPacteVecu });
        }
        else definirTribunal({ statut: 'erreur', erreur: e instanceof Error ? e.message : String(e) });
      });
  }, [definirTribunal]);

  const lancer = useCallback(() => {
    if (!decision) return;
    setAnimer(true);
    setEtapesVisibles(0);
    setProgression(null);
    definirTribunal({ statut: 'chargement' });
    let procesAccepte = false;
    suivre((signal) => jugerDecision(profil.id, decision, {
      signal,
      calibrage: reponsesPacteVecu,
      onProgression: setProgression,
      onAccepte: (procesId) => {
        procesAccepte = true;
        definirTribunal({ statut: 'chargement', procesId });
      },
    }), () => procesAccepte);
  }, [decision, definirTribunal, profil.id, reponsesPacteVecu, suivre]);

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

  // Retour sur l'écran (ou page rechargée) pendant un procès en direct : on reprend sa relecture,
  // sans relancer de procès (il a continué sur la Lambda).
  const procesEnCours = tribunal.statut === 'chargement' ? tribunal.procesId : undefined;
  useEffect(() => {
    if (!decision || !procesEnCours || suivi.current) return;
    setAnimer(true);
    suivre((signal) => reprendreProces(profil.id, decision, procesEnCours, { signal, onProgression: setProgression }), () => true);
  }, [decision, procesEnCours, profil.id, suivre]);

  // Quitter l'écran arrête la relecture de la progression. Le mode strict de React démonte puis
  // remonte aussitôt l'écran en développement : on n'interrompt qu'un vrai départ.
  const monte = useRef(false);
  useEffect(() => {
    monte.current = true;
    return () => {
      monte.current = false;
      setTimeout(() => { if (!monte.current) suivi.current?.abort(); }, 0);
    };
  }, []);

  useEffect(() => {
    if (!animer || !resultat) return undefined;
    if (mouvementReduit()) {
      setEtapesVisibles(resultat.trace.length);
      setAnimer(false);
      return undefined;
    }
    if (etapesVisibles >= resultat.trace.length) {
      const fin = setTimeout(() => setAnimer(false), DUREE_FIN_MS);
      return () => clearTimeout(fin);
    }
    const suivante = setTimeout(() => setEtapesVisibles((n) => n + 1), DUREE_ETAPE_RELECTURE_MS);
    return () => clearTimeout(suivante);
  }, [animer, resultat, etapesVisibles]);

  // Pièces du dossier : procès (et questions déjà archivées), questions de cette session, calculs du Greffier.
  const pieces: Piece[] = useMemo(() => [
    ...(resultat?.pieces ?? []),
    ...etat.echanges.flatMap((e) => e.piecesAjoutees),
    ...etat.piecesQuestions,
  ], [resultat, etat.echanges, etat.piecesQuestions]);
  const echanges = useMemo(() => [...(resultat?.echanges ?? []), ...etat.echanges], [resultat, etat.echanges]);

  // Réveille la Lambda dès l'ouverture : la première vérification n'attend pas un démarrage à froid.
  useEffect(() => reveillerLambda(resultat?.procesId), [resultat?.procesId]);

  useEffect(() => {
    if (!questionEnCours) return undefined;
    const minuterie = setInterval(() => setSecondesQuestion(Math.round((Date.now() - questionEnCours.debut) / 1000)), 1000);
    return () => clearInterval(minuterie);
  }, [questionEnCours]);
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
          raisonPacteVecu={tribunal.erreur}
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
    let chargement: PropsChargement;
    if (resultat && !MODE_DIRECT) {
      // Démonstration : la trace enregistrée, relue étape par étape.
      chargement = {
        mode: 'relecture', debut, dureeEtapeMs: DUREE_ETAPE_RELECTURE_MS,
        phase: phaseEnRelecture(resultat.trace, etapesVisibles),
        etapes: resultat.trace.slice(0, etapesVisibles),
        termine: etapesVisibles >= resultat.trace.length,
      };
    } else if (resultat) {
      chargement = { mode: 'direct', debut, phase: null, etapes: resultat.trace, termine: true };
    } else {
      chargement = {
        mode: MODE_DIRECT ? 'direct' : 'relecture', debut, dureeEtapeMs: DUREE_ETAPE_RELECTURE_MS,
        phase: progression?.phase ?? null, etapes: progression?.etapes ?? [], termine: false,
        activite: progression?.activite, avis: progression?.avis,
      };
    }
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal">
        {/* Paysage (#103) : les phases à gauche, le dossier instruit à droite. */}
        <div className={`${styles.corpsLarge} ${styles.attente}`}>
          <ChargementTribunal {...chargement} />
          <DossierInstruit decision={libelleDecision(decision)} regles={profil.pacte.regles} etapes={chargement.etapes} />
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
  const envoyer = async (e: FormEvent) => {
    e.preventDefault();
    const texte = question.trim();
    if (!texte || questionEnCours) return;
    const correspondante = questions.find((q) => q.libelle.toLowerCase() === texte.toLowerCase());
    setQuestion('');
    if (correspondante) {
      poser(correspondante);
      return;
    }
    if (!questionLibreDisponible(resultat.procesId) || !resultat.procesId) {
      setNoteQuestion(true);
      return;
    }
    setNoteQuestion(false);
    setErreurQuestion(null);
    setSecondesQuestion(0);
    setQuestionEnCours({ question: texte, debut: Date.now() });
    try {
      const { echange, pieces: nouvelles } = await poserQuestion(resultat.procesId, texte);
      ajouterEchange(adapterEchange(echange, nouvelles));
    } catch (err) {
      setErreurQuestion(err instanceof Error ? err.message : String(err));
      setQuestion(texte);
    } finally {
      setQuestionEnCours(null);
    }
  };

  return (
    <>
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal" inerte={Boolean(pieceOuverte)}>
        <div className={styles.corpsLarge}>
          <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
          <div className={styles.titre}>
            <p className="t-etiquette c-500">
              Audience n° {resultat.audience}
              {manquantes ? ` · ${manquantes} donnée${manquantes > 1 ? 's' : ''} manquante${manquantes > 1 ? 's' : ''}` : ''}
              {MODE_DIRECT ? '' : ' · procès enregistré'}
            </p>
            <h1 className="t-h1">{resultat.titre}</h1>
          </div>

          <section className={styles.bilan} aria-labelledby="titre-bilan">
            <div className={styles.resume}>
              <div className={styles.comptes}>
                <h2 className="t-intertitre" id="titre-bilan">Bilan du Greffier</h2>
                {comptes.filter(({ n }) => n > 0).map(({ statut, n }) => (
                  <span key={statut} className={styles.compte}>
                    <span className="t-tableau-fort">{n}</span>
                    <Statut type={statut} />
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
            <Repli id="repli-trace" titre="Comment le Tribunal a travaillé" sousTitre={`${resultat.trace.length} étapes`}>
              <ol className={styles.chronologie}>
                {resultat.trace.map((e, i) => (
                  <li key={i} className={styles.etapeChrono}>
                    <span className={`${styles.pastilleChrono} ${e.etat === 'signalement' ? styles.pastilleSignalement : ''}`} aria-hidden="true">
                      <Icone nom={e.etat === 'signalement' ? 'alerte' : 'check'} taille={14} />
                    </span>
                    <span className={styles.texteChrono}>
                      <span className="t-petit c-500">{e.role}{e.etat === 'signalement' && <span className="visuellement-cache"> (signalement)</span>}</span>
                      <span className="t-corps-fort">{e.titre}</span>
                      <code className="t-trace c-500">{e.appel}</code>
                      {e.raison && <span className="t-petit c-700">Raison : {e.raison}</span>}
                    </span>
                    {e.sortie && <PastillePiece code={e.sortie} onOuvrir={ouvrirPiece} />}
                  </li>
                ))}
              </ol>
            </Repli>
            <Repli id="repli-pieces" titre="Pièces à conviction" sousTitre={`${pieces.length} pièces`}>
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
                maxLength={500}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Posez votre question : les agents répondent avec les pièces du dossier"
              />
              <Bouton variante="secondaire" fleche={false} type="submit" disabled={Boolean(questionEnCours)}>
                {questionEnCours ? 'Instruction…' : 'Envoyer'}
              </Bouton>
            </form>
            {noteQuestion && (
              <p className="t-petit c-700" role="status">
                Une question libre va au vrai Tribunal : l'orchestrateur Bedrock choisit ses outils et ajoute des pièces, puis le
                Greffier vérifie chaque chiffre. Elle n'est envoyée qu'en mode direct (appels payants). Les questions suggérées
                ci-dessus sont calculées par le Greffier, sans IA.
              </p>
            )}
            {questionEnCours && (
              <p className={`t-petit c-700 ${styles.enCoursQuestion}`} role="status">
                Le Tribunal instruit votre question « {questionEnCours.question} »… {secondesQuestion ? `${secondesQuestion} s` : ''}
              </p>
            )}
            {erreurQuestion && (
              <Message type="Violation" titre="La question n'a pas pu être instruite">
                <p>{erreurQuestion}</p>
              </Message>
            )}
            {echanges.length > 0 && (
              <ol className={styles.echanges} aria-live="polite">
                {echanges.map((e, n) => (
                  <li key={`${n}-${e.question}`} className={styles.echange}>
                    <p className="t-petit-fort c-500">Question {n + 1} : « {e.question} »</p>
                    <ol className={styles.reponsesEchange}>
                      {e.arguments.map((a) => (
                        <li key={a.texte} className={`${styles.reponseEchange} ${a.camp === 'Procureur' ? styles.reponseProcureur : styles.reponseAvocat}`}>
                          <p className={styles.provenanceArgument}>
                            <span className="t-petit-fort">{a.camp}</span>
                            <Provenance type={a.provenance} />
                            {a.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={ouvrirPiece} />)}
                          </p>
                          <p className="t-corps">{a.texte}</p>
                        </li>
                      ))}
                    </ol>
                    <p className={styles.provenanceArgument}>
                      <IconeStatut type={e.argumentsRejetes.length ? 'À vérifier' : 'Conforme'} taille={14} />
                      <span className="t-petit c-700">Greffier : {e.controle}</span>
                      {e.piecesAjoutees.length > 0 && <span className="t-petit c-700"> · pièces ajoutées :</span>}
                      {e.piecesAjoutees.map((p) => <PastillePiece key={p.code} code={p.code} onOuvrir={ouvrirPiece} />)}
                    </p>
                    {e.argumentsRejetes.map((a) => (
                      <p key={a.texte} className={styles.rejete}>
                        <IconeStatut type="Violation" taille={14} />
                        <span className="t-petit"><strong>{a.camp}</strong> · « {a.texte} » — écarté : {a.raison}</span>
                      </p>
                    ))}
                  </li>
                ))}
              </ol>
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
