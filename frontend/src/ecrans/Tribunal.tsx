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
import { IconeStatut, PastillePiece, Provenance } from '../components/Etiquettes';
import { LienRetour, Message } from '../components/Elements';
import { Icone } from '../components/Icone';
import { TiroirPiece } from '../components/TiroirPiece';
import { LimitesDonnees } from '../components/Limites';
import { TrompezLeGreffier } from '../components/TrompezLeGreffier';
import { date } from '../lib/format';
import { libelleDecision } from '../domaine/decision';
import { resultatCalibrage } from '../domaine/calibrage';
import { phaseEnRelecture } from '../domaine/progression';
import { LIBELLES_COURTS, accroche, regrouperDebat, type ArgumentNumerote } from '../domaine/debat';
import { GROUPES, bilanGreffier, type Groupe } from '../domaine/bilan';
import { donneesCalibrage } from '../api/donnees';
import { questionsSuggerees, repondre, type QuestionSuggeree } from '../domaine/questions';
import { useEtatProfil } from '../state/store';
import { useTables } from '../state/useTables';
import styles from './Tribunal.module.css';

/** Relecture d'un procès enregistré : rythme fixe, annoncé à l'écran (#90). */
const DUREE_ETAPE_RELECTURE_MS = 500;
/** Toutes les phases cochées restent visibles un instant avant le résultat. */
const DUREE_FIN_MS = 800;

const TONS_BILAN = { violation: styles.bilanViolation, a_juger: styles.bilanAJuger, conforme: styles.bilanConforme };
const COMPTES_BILAN: Record<Groupe, string> = { enfreint: styles.tonEnfreint, a_juger: styles.tonAJuger, verifie: styles.tonVerifie };
const STATUT_DU_GROUPE: Record<Groupe, 'Violation' | 'À vérifier' | 'Conforme'> = { enfreint: 'Violation', a_juger: 'À vérifier', verifie: 'Conforme' };
const LIBELLES_COMPTES: Record<Groupe, (n: number) => string> = {
  enfreint: (n) => (n > 1 ? 'enfreints' : 'enfreint'),
  a_juger: () => 'à juger',
  verifie: (n) => (n > 1 ? 'vérifiés' : 'vérifié'),
};

function mouvementReduit(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** Espaces insécables dans « 188 291 $ » et « −29,0 % » : un montant n'est jamais coupé en fin de ligne. */
export function sansCoupure(texte: string): string {
  return texte.replace(/(\d) (?=\d{3}(?!\d))/g, '$1\u202f').replace(/(\d) (?=[$%])/g, '$1\u00a0');
}

/** Un argument sur la scène : sa conclusion en gras, la preuve dessous, puis ses pièces. */
function Plaidoyer({ argument, surligne, onOuvrir }: {
  argument: Argument;
  surligne: boolean;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const [preuve, setPreuve] = useState(false);
  const { tete, suite } = accroche(sansCoupure(argument.texte));
  const ouverte = preuve || surligne;
  return (
    <article className={`${styles.plaidoyer} ${surligne ? styles.plaidoyerSurligne : ''}`}>
      <p className={`t-corps ${styles.conclusion}`}>{tete}</p>
      {suite && ouverte && <p className={`t-petit c-700 ${styles.preuve}`}>{suite}</p>}
      <p className={styles.provenanceArgument}>
        <Provenance type={argument.provenance} />
        {argument.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={onOuvrir} />)}
        {suite && (
          <button type="button" className={styles.voirPreuve} aria-expanded={ouverte} onClick={() => setPreuve((p) => !p)}>
            {ouverte ? 'Masquer' : 'Voir la preuve'}
          </button>
        )}
      </p>
    </article>
  );
}

/** Un côté de la barre : le Procureur (contre) ou l'Avocat (pour), et ce qu'il plaide sur ce point. */
function Tribune({ camp, args, surlignes, onOuvrir }: {
  camp: 'Procureur' | 'Avocat';
  args: ArgumentNumerote[];
  surlignes: Set<string>;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const procureur = camp === 'Procureur';
  return (
    <div className={`${styles.tribune} ${procureur ? styles.tribuneProcureur : styles.tribuneAvocat}`}>
      <div className={styles.enteteTribune}>
        <span className={styles.blason} aria-hidden="true">{procureur ? 'P' : 'A'}</span>
        <span className={styles.roleTribune}>
          <span className={styles.nomCamp}>{camp}</span>
          <span className="t-petit c-500">{procureur ? 'contre la décision' : 'pour la décision'}</span>
        </span>
      </div>
      {args.length ? (
        <div className={styles.plaidoyers}>
          {args.map(({ argument, numero }) => (
            <Plaidoyer key={argument.texte} argument={argument} surligne={surlignes.has(`${camp}-${numero}`)} onOuvrir={onOuvrir} />
          ))}
        </div>
      ) : (
        <p className={styles.silence}>{procureur ? 'Le Procureur' : 'L’Avocat'} garde le silence sur ce point.</p>
      )}
    </div>
  );
}

/**
 * Le débat en salle d'audience : un point à la fois, sans défilement. Le sommaire liste les
 * points (deux pastilles disent quel camp a parlé) ; la scène met le Procureur et l'Avocat
 * face à face de part et d'autre de la balance. Flèches ← → pour passer d'un point à l'autre.
 */
function Debat({ procureur, avocat, surlignes, onOuvrir }: {
  procureur: Argument[];
  avocat: Argument[];
  surlignes: Set<string>;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const points = useMemo(() => regrouperDebat(procureur, avocat), [procureur, avocat]);
  const [rang, setRang] = useState(0);
  const onglets = useRef<(HTMLButtonElement | null)[]>([]);
  const actuel = points[Math.min(rang, points.length - 1)];

  // Une pièce ouverte amène sur le premier point dont un argument la cite.
  const cleSurlignes = [...surlignes].join(',');
  useEffect(() => {
    if (!cleSurlignes) return;
    const cles = new Set(cleSurlignes.split(','));
    const cible = points.findIndex((p) => [...p.procureur.map((a) => `Procureur-${a.numero}`), ...p.avocat.map((a) => `Avocat-${a.numero}`)]
      .some((cle) => cles.has(cle)));
    if (cible >= 0) setRang(cible);
  }, [cleSurlignes, points]);

  // L'onglet du point affiché reste visible dans la bande, même sur téléphone ; pas au
  // chargement, pour ne pas faire défiler la page jusqu'au débat.
  const premierAffichage = useRef(true);
  useEffect(() => {
    if (premierAffichage.current) {
      premierAffichage.current = false;
      return;
    }
    onglets.current[rang]?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [rang]);

  if (!actuel) return null;
  const borner = (r: number) => (r + points.length) % points.length;
  const aller = (nouveau: number, focus = false) => {
    setRang(borner(nouveau));
    if (focus) onglets.current[borner(nouveau)]?.focus();
  };
  // Les flèches partent du rang courant, même après plusieurs clics rapides.
  const decaler = (pas: number) => setRang((r) => borner(r + pas));
  const auClavier = (evenement: React.KeyboardEvent) => {
    const sauts: Record<string, number> = { ArrowRight: rang + 1, ArrowLeft: rang - 1, Home: 0, End: points.length - 1 };
    if (!(evenement.key in sauts)) return;
    evenement.preventDefault();
    aller(sauts[evenement.key], true);
  };

  return (
    <section className={styles.debat} aria-labelledby="titre-debat">
      <h2 className="visuellement-cache" id="titre-debat">L’audience : le débat point par point</h2>
      <div className={styles.enteteDebat}>
      <div className={styles.sommaire} role="tablist" aria-label="Points du débat" onKeyDown={auClavier}>
        {points.map((point, i) => (
          <button
            key={point.theme}
            ref={(el) => { onglets.current[i] = el; }}
            type="button"
            role="tab"
            id={`onglet-${point.theme}`}
            aria-selected={i === rang}
            aria-controls="scene-debat"
            tabIndex={i === rang ? 0 : -1}
            className={`${styles.onglet} ${i === rang ? styles.ongletActif : ''}`}
            onClick={() => aller(i)}
          >
            <span className={styles.numeroOnglet}>{i + 1}</span>
            <span>{LIBELLES_COURTS[point.theme]}</span>
            <span className={styles.voix} aria-hidden="true">
              <span className={`${styles.voixProcureur} ${point.procureur.length ? '' : styles.voixMuette}`} />
              <span className={`${styles.voixAvocat} ${point.avocat.length ? '' : styles.voixMuette}`} />
            </span>
          </button>
        ))}
      </div>
        <p className={styles.legendeDebat}>
          <span className={styles.legendeProcureur}>Procureur · contre · {procureur.length}</span>
          <span className={styles.legendeAvocat}>Avocat · pour · {avocat.length}</span>
        </p>
      </div>

      <div id="scene-debat" role="tabpanel" aria-labelledby={`onglet-${actuel.theme}`} className={styles.scene}>
        <div className={styles.enteteScene}>
          <div className={styles.questionScene}>
            <p className={styles.compteurPoint}>Point {rang + 1} sur {points.length}</p>
            <h3 className={`t-h2 ${styles.question}`} aria-live="polite">{actuel.question}</h3>
          </div>
          <div className={styles.navigationScene}>
            <button type="button" className={styles.fleche} onClick={() => decaler(-1)} aria-label="Point précédent">
              <Icone nom="fleche-gauche" taille={18} />
            </button>
            <button type="button" className={styles.fleche} onClick={() => decaler(1)} aria-label="Point suivant">
              <Icone nom="fleche-droite" taille={18} />
            </button>
          </div>
        </div>
        <div key={actuel.theme} className={styles.arene}>
          <Tribune camp="Procureur" args={actuel.procureur} surlignes={surlignes} onOuvrir={onOuvrir} />
          <div className={styles.barre} aria-hidden="true">
            <span className={styles.balance}><Icone nom="balance" taille={22} /></span>
          </div>
          <Tribune camp="Avocat" args={actuel.avocat} surlignes={surlignes} onOuvrir={onOuvrir} />
        </div>
      </div>

      <LimitesDonnees ecran="tribunal" titre="Ce que ce procès ne dit pas" />
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
  const bilan = bilanGreffier(resultat.controles, resultat.contrat);
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

          <section className={`${styles.bilan} ${TONS_BILAN[bilan.ton]}`} aria-labelledby="titre-bilan">
            <span className={styles.iconeBilan} aria-hidden="true">
              <Icone nom={bilan.ton === 'violation' ? 'interdit' : bilan.ton === 'a_juger' ? 'alerte' : 'check'} taille={20} />
            </span>
            <div className={styles.resume}>
              <p className={styles.surtitreBilan}>Le Greffier a vérifié votre décision · calcul Python, sans IA</p>
              <h2 className={`t-panneau ${styles.verdictBilan}`} id="titre-bilan">{bilan.verdict}</h2>
              {bilan.explication && <p className="t-corps c-700">{bilan.explication}</p>}
            </div>
            <div className={styles.coteBilan}>
              <p className={styles.comptesBilan}>
                {GROUPES.filter((g) => bilan.comptes[g.id] > 0).map((g) => (
                  <span key={g.id} className={`${styles.compteBilan} ${COMPTES_BILAN[g.id]}`}>
                    {bilan.comptes[g.id]} {LIBELLES_COMPTES[g.id](bilan.comptes[g.id])}
                  </span>
                ))}
              </p>
              <button type="button" className={styles.voirControles} aria-expanded={controlesOuverts} aria-controls="liste-controles" onClick={() => setControlesOuverts((o) => !o)}>
                {controlesOuverts ? 'Masquer le détail' : 'Voir le détail'}
                <Icone nom={controlesOuverts ? 'chevron-haut' : 'chevron-bas'} taille={14} />
              </button>
            </div>
            <div id="liste-controles" className={styles.controles} hidden={!controlesOuverts}>
              {reglePrincipale && (
                <p className={`t-petit c-700 ${styles.rappelRegle}`}>
                  Règle que vous avez signée le {date(resultat.contrat.pacte.date_signature)} (Pacte §{principal!.paragraphe}) :
                  « {reglePrincipale.libelle} ».
                </p>
              )}
              {GROUPES.map((g) => {
                const items = bilan.controles.filter((c) => c.groupe === g.id);
                if (!items.length) return null;
                return (
                  <div key={g.id} className={styles.groupeControles}>
                    <p className={styles.titreGroupe}>
                      <span className={`t-petit-fort ${COMPTES_BILAN[g.id]}`}>{g.titre} · {items.length}</span>
                      <span className="t-petit c-500">{g.aide}</span>
                    </p>
                    <ul className={styles.listeControles}>
                      {items.map((c) => (
                        <li key={`${c.regle}-${c.titre}`} className={styles.controle}>
                          <IconeStatut type={STATUT_DU_GROUPE[c.groupe]} taille={16} />
                          <span className={styles.texteControle}>
                            <span className="t-petit-fort">
                              {c.titre}
                              {c.paragraphe !== undefined && <span className="c-500"> · Pacte §{c.paragraphe}</span>}
                            </span>
                            {c.detail && <span className="t-petit c-700">{c.detail}</span>}
                          </span>
                          <span className={styles.piecesControle}>
                            {c.pieces.map((p) => <PastillePiece key={p} code={p} onOuvrir={ouvrirPiece} />)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </section>

          <Debat procureur={procureur} avocat={avocat} surlignes={surlignes} onOuvrir={ouvrirPiece} />

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
