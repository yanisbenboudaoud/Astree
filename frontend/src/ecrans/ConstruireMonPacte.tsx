/**
 * « Construire mon Pacte » (#86) : questionnaire investisseur, portefeuille, aperçu et signature.
 *
 * Une question par écran, par sections (Horizon · Capacité · Tolérance · Expérience ·
 * Préférences). Les questions et les cartes viennent du pipeline ; le Pacte est calculé par
 * Python (`POST /profil` en direct, exemple préenregistré en démonstration). Une fois signé,
 * le profil est disponible pour tous les écrans, à commencer par « Revivez 4 jours ».
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MODE_DIRECT } from '../api/config';
import { TITRES, libelleProfilRisque } from '../api/donnees';
import {
  PacteNonDisponible, QUESTIONS, ReponsesRefusees, apercuPacte, saisieDemo, signerPacte,
  type CarteFourchette, type LigneSaisie, type Question, type Reponses, type ResultatPacte, type SaisiePacte, type ValeurReponse,
} from '../api/questionnaire';
import { Bouton } from '../components/Bouton';
import { Message } from '../components/Elements';
import { Provenance, Statut } from '../components/Etiquettes';
import { Gabarit, useTitre } from '../components/Gabarit';
import {
  basculerChoixMultiple, blocage, erreurPortefeuille, questionsPassees, raisonsRegle, reponsesNettoyees, sections,
  seuilModifiable, totalPoids, valeurDepuisPoints,
} from '../domaine/questionnaire';
import { date, dollars, horizon, nombre, pourcent } from '../lib/format';
import styles from './ConstruireMonPacte.module.css';

const MENTION = 'Simulation éducative. Ce questionnaire décrit vos propres règles ; il ne constitue pas un conseil financier.';
const CLE_STOCKAGE = 'astree.questionnaire.v1';
const NOM_PAR_DEFAUT = 'Investisseur';

type Etape = number | 'portefeuille' | 'apercu';

interface Brouillon {
  etape: Etape;
  reponses: Reponses;
  nom: string;
  capital: number;
  portefeuille: LigneSaisie[];
  modifications: Record<string, number>;
  /** Saisie remplie par « Remplir comme un profil de test » (réponses préenregistrées, Fictif). */
  demo: boolean;
}

const VIDE: Brouillon = {
  etape: 0, reponses: {}, nom: '', capital: 100_000, portefeuille: [{ ticker: '', poids: 1 }], modifications: {}, demo: false,
};

function lireBrouillon(): Brouillon {
  try {
    const brut = sessionStorage.getItem(CLE_STOCKAGE);
    return brut ? { ...VIDE, ...(JSON.parse(brut) as Partial<Brouillon>) } : VIDE;
  } catch {
    return VIDE;
  }
}

function useBrouillon() {
  const [brouillon, setBrouillon] = useState<Brouillon>(lireBrouillon);
  useEffect(() => {
    try {
      sessionStorage.setItem(CLE_STOCKAGE, JSON.stringify(brouillon));
    } catch {
      /* stockage indisponible : le brouillon reste en mémoire */
    }
  }, [brouillon]);
  const modifier = (partiel: Partial<Brouillon>) => setBrouillon((b) => ({ ...b, ...partiel }));
  return [brouillon, modifier] as const;
}

function saisieDe(b: Brouillon): SaisiePacte {
  const saisie: SaisiePacte = {
    nom: b.nom.trim() || NOM_PAR_DEFAUT,
    capital: b.capital,
    portefeuille: b.portefeuille.filter((l) => l.ticker),
    reponses: reponsesNettoyees(b.reponses),
  };
  if (Object.keys(b.modifications).length) saisie.modifications = b.modifications;
  return saisie;
}

export function ConstruireMonPacte() {
  useTitre('Construire mon Pacte');
  const [brouillon, modifier] = useBrouillon();
  const titre = useRef<HTMLHeadingElement>(null);
  const premierRendu = useRef(true);

  // À chaque étape, la page remonte et le focus va au titre : le lecteur d'écran lit la nouvelle question.
  useEffect(() => {
    window.scrollTo?.(0, 0);
    if (premierRendu.current) {
      premierRendu.current = false;
      return;
    }
    titre.current?.focus();
  }, [brouillon.etape]);

  const remplirDemo = () => {
    const demo = saisieDemo();
    modifier({ ...VIDE, etape: 'apercu', reponses: demo.reponses, nom: demo.nom, capital: demo.capital, portefeuille: demo.portefeuille, demo: true });
  };
  const recommencer = () => modifier({ ...VIDE });

  return (
    <Gabarit>
      <div className={styles.corps}>
        <p className={`t-petit c-700 ${styles.mention}`} role="note">{MENTION}</p>
        {typeof brouillon.etape === 'number' && (
          <EtapeQuestion brouillon={brouillon} modifier={modifier} titre={titre} onDemo={remplirDemo} />
        )}
        {brouillon.etape === 'portefeuille' && <EtapePortefeuille brouillon={brouillon} modifier={modifier} titre={titre} />}
        {brouillon.etape === 'apercu' && <EtapeApercu brouillon={brouillon} modifier={modifier} titre={titre} onRecommencer={recommencer} />}
      </div>
    </Gabarit>
  );
}

interface ProprietesEtape {
  brouillon: Brouillon;
  modifier: (partiel: Partial<Brouillon>) => void;
  titre: React.RefObject<HTMLHeadingElement>;
}

// --- Questions -------------------------------------------------------------------------

function Progression({ index }: { index: number }) {
  const parties = sections(QUESTIONS);
  const total = QUESTIONS.length;
  const courante = parties.find((s) => index >= s.debut && index < s.debut + s.nombre);
  return (
    <div className={styles.progression}>
      <ol className={styles.sections} aria-label="Sections du questionnaire">
        {parties.map((s) => {
          const etat = index >= s.debut + s.nombre ? 'faite' : s === courante ? 'courante' : 'a_venir';
          return (
            <li key={s.titre} className={styles[etat]} aria-current={s === courante ? 'step' : undefined}>
              {s.titre.split(' : ')[0]}
            </li>
          );
        })}
      </ol>
      <div className={styles.barre} role="progressbar" aria-label="Progression" aria-valuemin={1} aria-valuemax={total} aria-valuenow={index + 1}
        aria-valuetext={`Question ${index + 1} sur ${total}`}>
        <span style={{ width: `${((index + 1) / total) * 100}%` }} />
      </div>
      <p className="t-petit c-700" aria-live="polite">Question {index + 1} sur {total}{courante ? ` · ${courante.titre}` : ''}</p>
    </div>
  );
}

function EtapeQuestion({ brouillon, modifier, titre, onDemo }: ProprietesEtape & { onDemo: () => void }) {
  const index = brouillon.etape as number;
  const question = QUESTIONS[index];
  const valeur = brouillon.reponses[question.id];
  const [erreur, setErreur] = useState<string | null>(null);
  const idErreur = useId();
  useEffect(() => setErreur(null), [index]);

  const repondre = (v: ValeurReponse) => {
    setErreur(null);
    modifier({ reponses: { ...brouillon.reponses, [question.id]: v }, demo: false });
  };
  const aller = (etape: Etape) => modifier({ etape });
  const suivante: Etape = index + 1 < QUESTIONS.length ? index + 1 : 'portefeuille';
  const suivant = () => {
    const probleme = blocage(question, valeur);
    if (probleme) {
      setErreur(probleme);
      return;
    }
    aller(suivante);
  };
  const passer = () => {
    const reponses = { ...brouillon.reponses };
    delete reponses[question.id];
    modifier({ reponses, etape: suivante });
  };

  return (
    <>
      <div className={styles.entete}>
        <p className="t-etiquette c-500">Construire mon Pacte</p>
        <Progression index={index} />
      </div>
      <form className={styles.question} onSubmit={(e) => { e.preventDefault(); suivant(); }} noValidate>
        <fieldset className={styles.fieldset} aria-describedby={erreur ? idErreur : undefined}>
          <legend className={styles.legende}>
            <h1 className="t-h1" ref={titre} tabIndex={-1}>{question.libelle}</h1>
            <span className="t-petit c-700">
              {question.obligatoire ? 'Obligatoire' : 'Facultative : vous pouvez la passer'}
              {question.type === 'choix_multiples' && ' · plusieurs choix possibles'}
            </span>
          </legend>
          <ChampReponse question={question} valeur={valeur} onRepondre={repondre} />
        </fieldset>
        {erreur && <p id={idErreur} className={`t-corps ${styles.erreur}`} role="alert">{erreur}</p>}
        <div className={styles.actions}>
          {index > 0 && <Bouton variante="secondaire" onClick={() => aller(index - 1)}>← Précédente</Bouton>}
          <span className={styles.espace} />
          {!question.obligatoire && <Bouton variante="tertiaire" onClick={passer}>Passer cette question</Bouton>}
          <Bouton variante="primaire" type="submit">{suivante === 'portefeuille' ? 'Passer au portefeuille' : 'Suivante'}</Bouton>
        </div>
      </form>
      {index === 0 && (
        <aside className={styles.demo} aria-label="Démonstration">
          <p className="t-petit c-700">
            Pour une démonstration reproductible : réponses préenregistrées d’un profil de test, avec leur portefeuille.
          </p>
          <Bouton variante="secondaire" compact onClick={onDemo}>Remplir comme un profil de test</Bouton>
          <Provenance type="Fictif" />
        </aside>
      )}
    </>
  );
}

function ChampReponse({ question, valeur, onRepondre }: { question: Question; valeur: ValeurReponse | undefined; onRepondre: (v: ValeurReponse) => void }) {
  const nom = useId();
  if (question.type === 'texte') {
    const texte = typeof valeur === 'string' ? valeur : '';
    return (
      <div className={styles.texte}>
        <label className="visuellement-cache" htmlFor={nom}>{question.libelle}</label>
        <textarea id={nom} rows={3} value={texte} maxLength={question.longueur_max} onChange={(e) => onRepondre(e.target.value)} />
        <span className="t-petit c-700" aria-live="polite">{texte.length} / {question.longueur_max} caractères</span>
      </div>
    );
  }
  if (question.type === 'cartes') {
    const cartes = question.cartes ?? [];
    return (
      <>
        <ul className={styles.cartes}>
          {cartes.map((carte) => (
            <li key={carte.id}>
              <label className={`${styles.carte} ${valeur === carte.id ? styles.choisie : ''}`}>
                <input type="radio" name={nom} value={carte.id} checked={valeur === carte.id} onChange={() => onRepondre(carte.id)} />
                <ContenuCarte carte={carte} />
              </label>
            </li>
          ))}
        </ul>
        {cartes[0] && (
          <p className={`t-petit c-700 ${styles.provenance}`}>
            <Provenance type="Fait" />
            <span>Prix réels du {date(cartes[0].periode[0])} au {date(cartes[0].periode[1])}, en CAD, pour {dollars(cartes[0].capital)} placés. Le passé ne prédit pas l’avenir.</span>
          </p>
        )}
      </>
    );
  }
  const multiple = question.type === 'choix_multiples';
  const choisis = Array.isArray(valeur) ? valeur : valeur ? [valeur] : [];
  return (
    <ul className={styles.choix}>
      {(question.choix ?? []).map((choix) => {
        const coche = choisis.includes(choix.id);
        return (
          <li key={choix.id}>
            <label className={`${styles.option} ${coche ? styles.choisie : ''}`}>
              <input
                type={multiple ? 'checkbox' : 'radio'}
                name={nom}
                value={choix.id}
                checked={coche}
                onChange={() => onRepondre(multiple ? basculerChoixMultiple(choisis, choix.id) : choix.id)}
              />
              <span className="t-corps">{choix.libelle}</span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

function ContenuCarte({ carte }: { carte: CarteFourchette }) {
  return (
    <span className={styles.contenuCarte}>
      <span className="t-corps-fort">{carte.libelle}</span>
      <span className="t-petit c-700">{carte.portefeuille.map((l) => `${l.ticker} ${nombre(l.poids * 100)} %`).join(' · ')}</span>
      <span className={styles.chiffresCarte}>
        <span>
          <span className="t-petit c-700">Au pire moment</span>
          <span className="t-tableau-fort">{dollars(carte.montant_pire_moment)}</span>
          <span className="t-petit c-700">({pourcent(carte.pire_baisse)})</span>
        </span>
        <span>
          <span className="t-petit c-700">À la fin</span>
          <span className="t-tableau-fort">{dollars(carte.valeur_finale)}</span>
        </span>
      </span>
    </span>
  );
}

// --- Portefeuille -----------------------------------------------------------------------

function EtapePortefeuille({ brouillon, modifier, titre }: ProprietesEtape) {
  const [erreur, setErreur] = useState<string | null>(null);
  const idNom = useId();
  const idCapital = useId();
  const lignes = brouillon.portefeuille;
  const total = totalPoids(lignes.filter((l) => l.ticker));
  const titresParClasse = useMemo(() => {
    const groupes = new Map<string, typeof TITRES>();
    for (const t of TITRES) groupes.set(t.classe, [...(groupes.get(t.classe) ?? []), t]);
    return [...groupes.entries()];
  }, []);

  const changerLigne = (i: number, partiel: Partial<LigneSaisie>) => {
    setErreur(null);
    modifier({ portefeuille: lignes.map((l, j) => (j === i ? { ...l, ...partiel } : l)), demo: false });
  };
  const continuer = () => {
    const probleme = erreurPortefeuille(lignes, brouillon.capital);
    if (probleme) {
      setErreur(probleme);
      return;
    }
    modifier({ etape: 'apercu', modifications: {} });
  };

  return (
    <>
      <div className={styles.entete}>
        <p className="t-etiquette c-500">Construire mon Pacte · dernière étape</p>
        <h1 className="t-h1" ref={titre} tabIndex={-1}>Votre portefeuille actuel</h1>
        <p className="t-corps c-700">
          Les titres de l’univers que vous détenez, et leur poids. Le capital est fictif : rien n’est acheté ni vendu.
        </p>
      </div>
      <form className={styles.question} onSubmit={(e) => { e.preventDefault(); continuer(); }} noValidate>
        <div className={styles.champs}>
          <label htmlFor={idNom} className="t-petit-fort">Votre prénom (facultatif)</label>
          <input id={idNom} type="text" maxLength={40} value={brouillon.nom} placeholder={NOM_PAR_DEFAUT}
            onChange={(e) => modifier({ nom: e.target.value, demo: false })} />
          <label htmlFor={idCapital} className="t-petit-fort">Capital fictif (CAD)</label>
          <input id={idCapital} type="number" min={1} step={1000} value={Number.isFinite(brouillon.capital) ? brouillon.capital : ''}
            onChange={(e) => modifier({ capital: e.target.valueAsNumber, demo: false })} />
        </div>
        <table className={styles.lignes}>
          <caption className="visuellement-cache">Titres du portefeuille et leur poids</caption>
          <thead>
            <tr><th scope="col" className="t-petit-fort">Titre</th><th scope="col" className="t-petit-fort">Poids (%)</th><th scope="col"><span className="visuellement-cache">Retirer</span></th></tr>
          </thead>
          <tbody>
            {lignes.map((ligne, i) => (
              <tr key={i}>
                <td>
                  <select aria-label={`Titre ${i + 1}`} value={ligne.ticker} onChange={(e) => changerLigne(i, { ticker: e.target.value })}>
                    <option value="">Choisir un titre…</option>
                    {titresParClasse.map(([classe, titres]) => (
                      <optgroup key={classe} label={classe}>
                        {titres.map((t) => <option key={t.ticker} value={t.ticker}>{t.nom} ({t.ticker})</option>)}
                      </optgroup>
                    ))}
                  </select>
                </td>
                <td>
                  <input type="number" aria-label={`Poids du titre ${i + 1}, en pourcentage`} min={0} max={100} step={1}
                    value={Number.isFinite(ligne.poids) ? Math.round(ligne.poids * 10000) / 100 : ''}
                    onChange={(e) => changerLigne(i, { poids: e.target.valueAsNumber / 100 })} />
                </td>
                <td>
                  {lignes.length > 1 && (
                    <Bouton variante="tertiaire" compact onClick={() => modifier({ portefeuille: lignes.filter((_, j) => j !== i) })}>
                      Retirer<span className="visuellement-cache"> le titre {i + 1}</span>
                    </Bouton>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className={styles.totalLigne}>
          <Bouton variante="secondaire" compact onClick={() => modifier({ portefeuille: [...lignes, { ticker: '', poids: 0 }] })}>Ajouter un titre</Bouton>
          <span className={`t-tableau-fort ${Math.abs(total - 1) > 0.0005 ? styles.texteErreur : ''}`} aria-live="polite">
            Total : {nombre(total * 100, 1)} %
          </span>
        </div>
        {erreur && <p className={`t-corps ${styles.erreur}`} role="alert">{erreur}</p>}
        <div className={styles.actions}>
          <Bouton variante="secondaire" onClick={() => modifier({ etape: QUESTIONS.length - 1 })}>← Questions</Bouton>
          <span className={styles.espace} />
          <Bouton variante="primaire" type="submit">Voir mon Pacte</Bouton>
        </div>
      </form>
    </>
  );
}

// --- Aperçu et signature ---------------------------------------------------------------------

function messageErreur(e: unknown): string[] {
  if (e instanceof ReponsesRefusees) return e.details;
  return [e instanceof Error ? e.message : String(e)];
}

function EtapeApercu({ brouillon, modifier, titre, onRecommencer }: ProprietesEtape & { onRecommencer: () => void }) {
  const navigate = useNavigate();
  const [resultat, setResultat] = useState<ResultatPacte | null>(null);
  const [erreur, setErreur] = useState<string[] | null>(null);
  const [nonDisponible, setNonDisponible] = useState(false);
  const [signature, setSignature] = useState<'attente' | 'envoi'>('attente');
  const saisie = useMemo(() => saisieDe(brouillon), [brouillon]);
  const cle = JSON.stringify(saisie);

  useEffect(() => {
    let actif = true;
    setErreur(null);
    apercuPacte(saisie)
      .then((r) => actif && setResultat(r))
      .catch((e) => {
        if (!actif) return;
        setNonDisponible(e instanceof PacteNonDisponible);
        setErreur(messageErreur(e));
      });
    return () => { actif = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- la saisie est comparée par sa forme JSON
  }, [cle]);

  const signer = async () => {
    setSignature('envoi');
    try {
      const signe = await signerPacte(saisie);
      try {
        sessionStorage.removeItem(CLE_STOCKAGE);
      } catch {
        /* rien à nettoyer */
      }
      window.scrollTo?.(0, 0);
      navigate(`/${signe.id}/pacte-vecu`);
    } catch (e) {
      setErreur(messageErreur(e));
      setSignature('attente');
    }
  };

  const passees = questionsPassees(QUESTIONS, brouillon.reponses);
  const profil = resultat?.profil;

  return (
    <>
      <div className={styles.entete}>
        <p className="t-etiquette c-500">Construire mon Pacte · aperçu</p>
        <h1 className="t-h1" ref={titre} tabIndex={-1}>Votre Pacte, tiré de vos réponses</h1>
        <p className="t-corps c-700">
          Chaque règle dit quelle réponse l’a produite. Relisez-les, changez un seuil si vous le souhaitez, puis signez :
          le Tribunal jugera ensuite vos décisions avec ces règles.
        </p>
        {brouillon.demo && (
          <p className={`t-petit c-700 ${styles.provenance}`}>
            <Provenance type="Fictif" /> Réponses préenregistrées d’un profil de test.
          </p>
        )}
      </div>

      {erreur && (
        <Message type="À vérifier" titre={nonDisponible ? 'Pacte non disponible en démonstration' : 'Le Pacte n’a pas pu être construit'}
          correction={{ libelle: 'Revenir aux questions', onClick: () => modifier({ etape: 0 }) }}>
          <ul className={styles.liste}>{erreur.map((m) => <li key={m}>{m}</li>)}</ul>
        </Message>
      )}
      {!erreur && !profil && <p className="t-corps c-700" role="status">Calcul du Pacte par le Tribunal…</p>}

      {profil && resultat && (
        <>
          <dl className={styles.resume}>
            <div><dt className="t-petit c-700">Profil de risque</dt><dd className="t-corps-fort">{libelleProfilRisque(profil.profil_risque)}</dd></div>
            <div><dt className="t-petit c-700">Horizon</dt><dd className="t-corps-fort">{horizon(profil.horizon_ans)}</dd></div>
            <div><dt className="t-petit c-700">Capital fictif</dt><dd className="t-corps-fort">{dollars(profil.capital_fictif_cad)} <Provenance type="Fictif" /></dd></div>
          </dl>

          <section className={styles.regles} aria-labelledby="titre-regles">
            <h2 className="t-h2" id="titre-regles">Les règles de votre Pacte</h2>
            <ol>
              {profil.pacte.regles.map((regle, i) => (
                <CarteRegle key={regle.id} numero={i + 1} regle={regle} resultat={resultat} brouillon={brouillon} modifier={modifier} />
              ))}
            </ol>
          </section>

          {(resultat.contradictions.length > 0 || resultat.bareme.controles.length > 0) && (
            <section className={styles.regles} aria-labelledby="titre-verifier">
              <h2 className="t-h2" id="titre-verifier">À vérifier avant de signer</h2>
              <ul className={styles.verifier}>
                {resultat.contradictions.map((c) => (
                  <li key={c.id}><Statut type="À vérifier" /><span className="t-corps">{c.message}</span></li>
                ))}
                {resultat.bareme.controles.map((c) => (
                  <li key={c.message}><Statut type="À vérifier" /><span className="t-corps">{c.message}</span></li>
                ))}
              </ul>
            </section>
          )}
          {passees.length > 0 && <p className="t-petit c-700">Questions passées : {passees.join(', ')}.</p>}
          {!MODE_DIRECT && (
            <p className="t-petit c-700">
              En démonstration, les seuils ne se modifient pas : le barème tourne en Python, sur la Lambda du Tribunal (mode direct).
            </p>
          )}

          <section className={styles.limites} aria-labelledby="titre-limites">
            <h2 className="t-petit-fort" id="titre-limites">Limites</h2>
            <ul className={`t-petit c-700 ${styles.liste}`}>
              {resultat.bareme.limites.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </section>

          <div className={styles.actions}>
            <Bouton variante="secondaire" onClick={() => modifier({ etape: 'portefeuille' })}>← Portefeuille</Bouton>
            <Bouton variante="tertiaire" onClick={onRecommencer}>Tout recommencer</Bouton>
            <span className={styles.espace} />
            <Bouton variante="primaire" onClick={signer} disabled={signature === 'envoi'} aria-describedby="date-signature">
              {signature === 'envoi' ? 'Signature…' : 'Signer mon Pacte'}
            </Bouton>
          </div>
          <p id="date-signature" className="t-petit c-700">
            Date de signature : {date(profil.pacte.date_signature)}. Ensuite : « Revivez 4 jours », pour mesurer votre limite sur de vrais jours de marché.
          </p>
        </>
      )}
    </>
  );
}

function CarteRegle({ numero, regle, resultat, brouillon, modifier }: {
  numero: number; regle: ResultatPacte['profil']['pacte']['regles'][number]; resultat: ResultatPacte;
} & Omit<ProprietesEtape, 'titre'>) {
  const raisons = raisonsRegle(regle.id, resultat.bareme, QUESTIONS);
  const detail = resultat.bareme.regles.find((r) => r.id === regle.id);
  const choisie = brouillon.modifications[regle.id] !== undefined;
  const modifiable = seuilModifiable(regle);
  const [points, setPoints] = useState('');
  const idChamp = useId();

  const appliquer = () => {
    const valeur = Number(points.replace(',', '.'));
    if (!Number.isFinite(valeur) || points.trim() === '') return;
    modifier({ modifications: { ...brouillon.modifications, [regle.id]: valeurDepuisPoints(regle, valeur) } });
    setPoints('');
  };
  const annuler = () => {
    const modifications = { ...brouillon.modifications };
    delete modifications[regle.id];
    modifier({ modifications });
  };

  return (
    <li className={styles.regle}>
      <div className={styles.enteteRegle}>
        <span className="t-petit-fort c-500">§{numero}</span>
        <h3 className="t-intertitre">{regle.libelle}</h3>
        {choisie ? <span className={`t-etiquette ${styles.choisiParVous}`}>Choisi par vous</span>
          : <Provenance type={detail?.etiquette === 'hypothese' ? 'Hypothèse' : 'Fait'} />}
      </div>
      {raisons.length > 0 && (
        <p className="t-petit c-700">Parce que vous avez répondu : {raisons.join(' ; ')}.</p>
      )}
      <details className={styles.justification}>
        <summary className="t-petit">Justification complète</summary>
        <p className="t-petit c-700">{regle.justification}</p>
      </details>
      {modifiable && MODE_DIRECT && (
        <div className={styles.modifier}>
          <label htmlFor={idChamp} className="t-petit">
            {regle.type === 'pire_baisse_max' ? 'Autre baisse maximale (en %)' : 'Autre plafond (en %)'}
          </label>
          <input id={idChamp} type="text" inputMode="decimal" value={points} size={6}
            placeholder={nombre(Math.abs(modifiable.valeur) * 100, 1)} onChange={(e) => setPoints(e.target.value)} />
          <Bouton variante="secondaire" compact onClick={appliquer}>Appliquer</Bouton>
          {choisie && <Bouton variante="tertiaire" compact onClick={annuler}>Revenir au barème</Bouton>}
        </div>
      )}
    </li>
  );
}
