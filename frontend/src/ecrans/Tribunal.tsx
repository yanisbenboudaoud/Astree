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
import { IconeStatut, PastillePiece, Provenance, TitresPieces } from '../components/Etiquettes';
import { DEFINITION_PIECE } from '../domaine/pieces';
import { LienRetour, Message } from '../components/Elements';
import { Icone } from '../components/Icone';
import { TiroirPiece } from '../components/TiroirPiece';
import { LimitesDonnees } from '../components/Limites';
import { TrompezLeGreffier } from '../components/TrompezLeGreffier';
import { date } from '../lib/format';
import { libelleDecision } from '../domaine/decision';
import { resultatCalibrage } from '../domaine/calibrage';
import { phaseEnRelecture } from '../domaine/progression';
import { regrouperDebat, type ArgumentNumerote } from '../domaine/debat';
import { GROUPES, bilanGreffier, type Groupe } from '../domaine/bilan';
import { pointsDeBascule } from '../domaine/verdict';
import { sourcesAffichees } from '../domaine/sources';
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

/** Un argument dans sa case : tout son texte, son étiquette et ses pièces sur la même ligne. */
function Plaidoyer({ argument, surligne, onOuvrir }: {
  argument: Argument;
  surligne: boolean;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  return (
    <p className={`${styles.plaidoyer} ${surligne ? styles.plaidoyerSurligne : ''}`}>
      <span className={styles.textePlaidoyer}>{sansCoupure(argument.texte)}</span>{' '}
      <span className={styles.provenanceArgument}>
        <Provenance type={argument.provenance} />
        {argument.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={onOuvrir} />)}
      </span>
    </p>
  );
}

/** Ce que plaide un camp sur un point, ou son silence. */
function Case({ camp, args, surlignes, onOuvrir }: {
  camp: 'Procureur' | 'Avocat';
  args: ArgumentNumerote[];
  surlignes: Set<string>;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const procureur = camp === 'Procureur';
  return (
    <div className={`${styles.case} ${procureur ? styles.caseProcureur : styles.caseAvocat}`}>
      <span className={styles.campMobile}>{procureur ? 'Procureur · contre' : 'Avocat · pour'}</span>
      {args.length ? (
        args.map(({ argument, numero }) => (
          <Plaidoyer key={argument.texte} argument={argument} surligne={surlignes.has(`${camp}-${numero}`)} onOuvrir={onOuvrir} />
        ))
      ) : (
        <p className={styles.silence}>Pas d’argument sur ce point.</p>
      )}
    </div>
  );
}

/**
 * Le débat d'un seul regard : une ligne par question, le Procureur à gauche, l'Avocat à droite.
 * Tout tient sur un écran, sans onglet ni défilement : on compare les deux camps sans rien retenir.
 */
function Debat({ procureur, avocat, surlignes, onOuvrir }: {
  procureur: Argument[];
  avocat: Argument[];
  surlignes: Set<string>;
  onOuvrir: (code: string, el: HTMLElement) => void;
}) {
  const points = useMemo(() => regrouperDebat(procureur, avocat), [procureur, avocat]);
  if (!points.length) return null;
  return (
    <section className={styles.debat} aria-labelledby="titre-debat">
      <div className={styles.enteteDebat}>
        <h2 className={`t-panneau ${styles.titreSolennel}`} id="titre-debat">Les débats</h2>
        <p className="t-petit c-700">
          Chaque argument cite ses pièces ; le Greffier a vérifié chacun de ses chiffres.
        </p>
      </div>
      <div className={styles.tableDebat} role="table" aria-label="Le débat, question par question">
        <div className={styles.ligneEntete} role="row">
          <span role="columnheader" className={styles.enteteQuestion}>Question</span>
          <span role="columnheader" className={`${styles.enteteCamp} ${styles.enteteProcureur}`}>
            <span className={styles.blason} aria-hidden="true">P</span>
            Procureur <span className={styles.sens}>contre la décision · {procureur.length}</span>
          </span>
          <span role="columnheader" className={`${styles.enteteCamp} ${styles.enteteAvocat}`}>
            <span className={styles.blason} aria-hidden="true">A</span>
            Avocat <span className={styles.sens}>pour la décision · {avocat.length}</span>
          </span>
          <span className={styles.balance} aria-hidden="true"><Icone nom="balance" taille={18} /></span>
        </div>
        {points.map((point, i) => (
          <div key={point.theme} className={styles.ligneDebat} role="row">
            <div role="rowheader">
              <h3 className={styles.questionDebat}>
                <span className={styles.numeroPoint} aria-hidden="true">{i + 1}</span>
                {point.question}
              </h3>
            </div>
            <div role="cell" className={styles.cellule}>
              <Case camp="Procureur" args={point.procureur} surlignes={surlignes} onOuvrir={onOuvrir} />
            </div>
            <div role="cell" className={styles.cellule}>
              <Case camp="Avocat" args={point.avocat} surlignes={surlignes} onOuvrir={onOuvrir} />
            </div>
          </div>
        ))}
      </div>
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
  const titresPieces = useMemo(() => Object.fromEntries(pieces.map((p) => [p.code, p.titre])), [pieces]);
  const echanges = useMemo(() => [...(resultat?.echanges ?? []), ...etat.echanges], [resultat, etat.echanges]);
  const sources = useMemo(() => sourcesAffichees(resultat?.sources ?? []), [resultat]);

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
  const controlesPacte = bilan.controles.filter((c) => c.paragraphe !== undefined);
  const controlesSysteme = bilan.controles.filter((c) => c.paragraphe === undefined);
  const bascules = pointsDeBascule(resultat);
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
    <TitresPieces.Provider value={titresPieces}>
      <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="tribunal" inerte={Boolean(pieceOuverte)}>
        <div className={styles.corpsLarge}>
          <LienRetour vers={`/${profil.id}/decision`}>Décision</LienRetour>
          <div className={styles.titre}>
            <p className="t-etiquette c-500">
              Audience n° {resultat.audience}
              {manquantes ? ` · ${manquantes} donnée${manquantes > 1 ? 's' : ''} manquante${manquantes > 1 ? 's' : ''}` : ''}
              {MODE_DIRECT ? '' : ' · procès enregistré'}
            </p>
            <h1 className={`t-h1 ${styles.titreSolennel}`}>{resultat.titre}</h1>
          </div>

          <section className={`${styles.bilan} ${TONS_BILAN[bilan.ton]}`} aria-labelledby="titre-bilan">
            <div className={styles.teteBilan}>
              <span className={styles.iconeBilan} aria-hidden="true">
                <Icone nom={bilan.ton === 'violation' ? 'interdit' : bilan.ton === 'a_juger' ? 'alerte' : 'check'} taille={20} />
              </span>
              <div className={styles.resume}>
                <p className={styles.surtitreBilan}>Le Greffier a vérifié votre décision · calcul Python, sans IA</p>
                <h2 className={`t-panneau ${styles.verdictBilan}`} id="titre-bilan">{bilan.verdict}</h2>
              </div>
            </div>

            <div className={styles.colonnesBilan}>
              <div className={styles.blocBilan}>
                <h3 className={styles.titreBloc}>
                  Votre Pacte, règle par règle
                  <span className="t-petit c-500"> · signé le {date(resultat.contrat.pacte.date_signature)}</span>
                </h3>
                <ul className={styles.listeControles}>
                  {controlesPacte.map((c) => (
                    <li key={`${c.regle}-${c.titre}`} className={styles.controle}>
                      <IconeStatut type={STATUT_DU_GROUPE[c.groupe]} taille={16} />
                      <span className={styles.texteControle}>
                        <span className="t-petit-fort">
                          {c.titre}
                          {c.paragraphe !== undefined && <span className="c-500"> · §{c.paragraphe}</span>}
                        </span>
                        {c.detail && <span className="t-petit c-700">{sansCoupure(c.detail)}</span>}
                      </span>
                      <span className={styles.piecesControle}>
                        {c.pieces.map((p) => <PastillePiece key={p} code={p} onOuvrir={ouvrirPiece} />)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {bascules.length > 0 && (
                <div className={`${styles.blocBilan} ${styles.bascule}`}>
                  <h3 className={styles.titreBloc}>Ce qui rendrait la décision conforme</h3>
                  <ul className={styles.listeBascules}>
                    {bascules.map((p) => (
                      <li key={p.regle} className={styles.ligneBascule}>
                        <span className="t-corps-fort">{sansCoupure(p.message)}</span>
                        <span className={styles.provenanceArgument}>
                          <span className="t-petit c-500">{p.paragraphe !== undefined ? `§${p.paragraphe} · ` : ''}Règle « {p.libelle} »</span>
                          {p.pieces.map((c) => <PastillePiece key={c} code={c} onOuvrir={ouvrirPiece} />)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {controlesSysteme.length > 0 && (
              <div className={styles.systeme}>
                <button type="button" className={styles.voirControles} aria-expanded={controlesOuverts} aria-controls="liste-controles" onClick={() => setControlesOuverts((o) => !o)}>
                  <Icone nom={controlesOuverts ? 'chevron-haut' : 'chevron-bas'} taille={16} />
                  Contrôles du Greffier sur les arguments
                  <span className={styles.resumeSysteme}>
                    {GROUPES.filter((g) => controlesSysteme.some((c) => c.groupe === g.id)).map((g) => {
                      const n = controlesSysteme.filter((c) => c.groupe === g.id).length;
                      return <span key={g.id} className={`${styles.compteBilan} ${COMPTES_BILAN[g.id]}`}>{n} {LIBELLES_COMPTES[g.id](n)}</span>;
                    })}
                  </span>
                </button>
                <ul id="liste-controles" className={styles.listeControles} hidden={!controlesOuverts}>
                  {controlesSysteme.map((c) => (
                    <li key={`${c.regle}-${c.titre}`} className={styles.controle}>
                      <IconeStatut type={STATUT_DU_GROUPE[c.groupe]} taille={16} />
                      <span className={styles.texteControle}>
                        <span className="t-petit-fort">{c.titre}</span>
                        {c.detail && <span className="t-petit c-700">{c.detail}</span>}
                      </span>
                      <span className={styles.piecesControle}>
                        {c.pieces.map((p) => <PastillePiece key={p} code={p} onOuvrir={ouvrirPiece} />)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
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

          <LimitesDonnees ecran="tribunal" titre="Ce que ce procès ne dit pas" ouvertParDefaut />

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

          <div className={styles.dossier}>
          <h2 className={`t-panneau ${styles.titreSolennel}`}>Le dossier</h2>
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
              <p className={`t-petit c-700 ${styles.definitionPieces}`}>{DEFINITION_PIECE}</p>
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
            {sources.length > 0 && (
              <Repli id="repli-sources" titre="D'où viennent les données" sousTitre={`${sources.length} sources`}>
                <ul className={styles.listeSources}>
                  {sources.map((s) => (
                    <li key={s.nom} className={styles.source}>
                      <span className="t-corps-fort">{s.nom}</span>
                      {s.details && <span className="t-petit c-500">{s.details}</span>}
                      {s.usage && <span className="t-petit c-700">{s.usage}</span>}
                      {(s.expliquees.length > 0 || s.regles.length > 0) && (
                        <ul className={styles.utilisations} aria-label={`Pourquoi ${s.nom} a servi`}>
                          {s.expliquees.map((p) => (
                            <li key={p.code} className={styles.utilisation}>
                              <PastillePiece code={p.code} onOuvrir={ouvrirPiece} />
                              <span className="t-petit c-700">{p.raison}</span>
                            </li>
                          ))}
                          {s.regles.map((r) => (
                            <li key={r} className={styles.utilisation}>
                              <span className="t-petit c-700">Contrôle de la règle « {r} »</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      {s.autres.length > 0 && (
                        <p className={styles.autresPieces}>
                          <span className="t-petit c-500">{s.expliquees.length > 0 ? 'Aussi dans' : 'Dans'}</span>
                          {s.autres.map((p) => <PastillePiece key={p.code} code={p.code} onOuvrir={ouvrirPiece} />)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </Repli>
            )}
            <Repli id="repli-greffier" titre="Mettre le Greffier à l’épreuve" sousTitre="Écrivez un argument chiffré : le Greffier vérifie chaque nombre, sans IA">
              <TrompezLeGreffier resultat={resultat} pieces={pieces} integre />
            </Repli>
          </div>
          </div>

          <div className={styles.barreVerdict} role="region" aria-label="Rendre votre verdict">
            <p className={styles.texteVerdict}>
              <span className={styles.titreSolennel}>Le Tribunal a terminé. À vous de juger.</span>
              <span className="t-petit c-700">
                {bilan.verdict}{bascules[0] ? ` · ${sansCoupure(bascules[0].message)}` : ''}
              </span>
            </p>
            <div className={styles.boutonsVerdict}>
              <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/decision`}>Modifier la décision</Bouton>
              <Bouton variante="primaire" onClick={() => navigate(`/${profil.id}/verdict`)}>Rendre mon verdict</Bouton>
            </div>
          </div>
        </div>
      </Gabarit>
      {pieceOuverte && createPortal(<TiroirPiece piece={pieceOuverte} onFermer={fermerPiece} />, document.body)}
    </TitresPieces.Provider>
  );
}
