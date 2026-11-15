/**
 * Écran « Revivez 4 jours » : le Pacte vécu (#68).
 *
 * L'utilisateur revit de vrais jours de baisse, en dollars, sans voir la suite, et répond
 * « je reste » ou « je vends ». Le seuil de pire baisse de son Pacte devient la baisse réelle
 * du dernier jour où il est resté. Les jours viennent de scripts/build_ui_series.py
 * (pipeline/calibrage.py) ; le Tribunal recalcule tout en Python à partir des réponses.
 */
import type { ReactNode } from 'react';
import type { Profil, QuestionCalibrage } from '../api/types';
import { donneesCalibrage, profil as profilDe } from '../api/donnees';
import { Gabarit, useTitre } from '../components/Gabarit';
import { GraphiqueValeur } from '../components/graphiques/GraphiqueValeur';
import { Bouton } from '../components/Bouton';
import { LienRetour, Message } from '../components/Elements';
import { Provenance } from '../components/Etiquettes';
import { date, dollars, horizon, nombre, part, pourcent, seuil as seuilTexte } from '../lib/format';
import { prochaineQuestion, resultatCalibrage, RESTE } from '../domaine/calibrage';
import { seuilPireBaisse } from '../domaine/pacte';
import { useEtatProfil } from '../state/store';
import styles from './Calibrage.module.css';

const LIBELLES_CHOIX: Record<string, Record<string, string>> = {
  baisse: { reste: 'Je reste investi', vend: 'Je vends tout' },
  capacite: { attendre: 'Oui, je pourrais attendre', pas_attendre: 'Non, c’est trop long' },
  crypto: { reste: 'Je garde ma crypto', vend: 'Je vends ma crypto' },
  valeurs: { garder: 'Je garde ma règle', assouplir: 'Je l’assouplirais' },
};

const REPONSES_COURTES: Record<string, string> = {
  reste: 'je reste', vend: 'je vends', attendre: 'je peux attendre', pas_attendre: 'je ne peux pas attendre',
  garder: 'je garde ma règle', assouplir: 'je l’assouplirais',
};

const aujourdhui = () => new Date().toISOString().slice(0, 10);

function annees(valeur: number): string {
  return `${nombre(valeur, 1)} an${valeur >= 2 ? 's' : ''}`;
}

function Question({ question, onRepondre }: { question: QuestionCalibrage; onRepondre: (choix: string) => void }) {
  let contenu: ReactNode;
  if (question.type === 'baisse') {
    contenu = (
      <>
        <div className={styles.enteteCarte}>
          <h2 className="t-h2">Le {date(question.date_jour)}</h2>
          <span className="t-petit c-500">{question.serie}</span>
        </div>
        <p className="t-corps">
          Depuis son sommet du {date(question.date_sommet)}, la valeur a baissé de{' '}
          <strong className={styles.baisse}>{pourcent(question.baisse)}</strong>. Vous ne savez pas ce qui se passe ensuite.
        </p>
        <p className={styles.montants}>
          <span className="t-tableau">{dollars(question.valeur_sommet)}</span>
          <span className={styles.fleche} aria-hidden="true">→</span>
          <span className="visuellement-cache">sont devenus</span>
          <span className="t-chiffre-moyen">{dollars(question.valeur_jour)}</span>
          <span className="t-petit c-500">sur votre capital, s’il était investi ainsi au sommet</span>
        </p>
        <GraphiqueValeur
          serie={question.historique}
          pointBas={{ date: question.date_jour, valeur: question.valeur_jour, recul: question.baisse }}
        />
        <p className="t-intertitre">Ce jour-là, que faites-vous ?</p>
      </>
    );
  } else if (question.type === 'capacite') {
    const duree = question.annees_retour === null
      ? 'elle n’était pas encore revenue à son sommet à la fin de la période'
      : `il a fallu ${annees(question.annees_retour)} pour revenir au sommet du ${date(question.date_sommet)}`;
    contenu = (
      <>
        <h2 className="t-h2">Pourriez-vous attendre ?</h2>
        <p className="t-corps">
          Après la baisse de {pourcent(question.baisse)} ({question.serie}), {duree}. Votre horizon est de{' '}
          {horizon(question.horizon_ans as number[])}.
        </p>
        <p className="t-intertitre">Pourriez-vous attendre aussi longtemps sans avoir besoin de cet argent ?</p>
      </>
    );
  } else if (question.type === 'crypto') {
    contenu = (
      <>
        <div className={styles.enteteCarte}>
          <h2 className="t-h2">Le {date(question.date_jour)}</h2>
          <span className="t-petit c-500">{question.serie}</span>
        </div>
        <p className="t-corps">
          Votre crypto représente {part(question.part)} de votre portefeuille. Depuis son sommet du {date(question.date_sommet)},
          elle a baissé de <strong className={styles.baisse}>{pourcent(question.baisse)}</strong>.
        </p>
        <p className={styles.montants}>
          <span className="t-tableau">{dollars(question.valeur_sommet)}</span>
          <span className={styles.fleche} aria-hidden="true">→</span>
          <span className="visuellement-cache">sont devenus</span>
          <span className="t-chiffre-moyen">{dollars(question.valeur_jour)}</span>
        </p>
        <p className="t-intertitre">Ce jour-là, que faites-vous ?</p>
      </>
    );
  } else {
    contenu = (
      <>
        <h2 className="t-h2">Vos valeurs ont-elles un prix ?</h2>
        <p className="t-corps">
          Votre Pacte dit : « {question.libelle} ». Si un titre exclu par cette règle avait rapporté davantage que votre
          portefeuille, la garderiez-vous ?
        </p>
      </>
    );
  }
  return (
    <section className={styles.carte} aria-label="Question en cours">
      {contenu}
      <div className={styles.choix}>
        {question.choix.map((choix) => (
          <Bouton key={choix} variante="secondaire" onClick={() => onRepondre(choix)}>
            {LIBELLES_CHOIX[question.type][choix] ?? choix}
          </Bouton>
        ))}
      </div>
    </section>
  );
}

export function Calibrage({ profil }: { profil: Profil }) {
  useTitre('Pacte vécu');
  const { etat, definirCalibrage } = useEtatProfil(profil.id);
  const donnees = donneesCalibrage(profil.id);
  const base = profilDe(profil.id) ?? profil;

  if (!donnees) {
    return (
      <Gabarit nomProfil={profil.nom} idProfil={profil.id}>
        <div className={styles.corps}>
          <LienRetour vers={`/${profil.id}/portefeuille`}>Portefeuille</LienRetour>
          <Message type="À vérifier" titre="Pacte vécu indisponible pour ce profil">
            <p>Les jours de marché de ce profil n’ont pas été générés (scripts/build_ui_series.py).</p>
          </Message>
        </div>
      </Gabarit>
    );
  }

  const reponses = etat.calibrage?.reponses ?? {};
  const question = prochaineQuestion(donnees, reponses);
  const resultat = resultatCalibrage(donnees, reponses);
  const repondre = (choix: string) => question && definirCalibrage({ reponses: { ...reponses, [question.id]: choix }, date: aujourdhui() });
  const recommencer = () => definirCalibrage(null);
  const seuilDeclare = seuilPireBaisse(base);
  const joursRepondus = resultat.jours.length;
  const demo = donnees.demo;
  const reponsesDemo = Boolean(demo) && JSON.stringify(Object.entries(reponses).sort()) === JSON.stringify(Object.entries(demo!.reponses).sort());

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id}>
      <div className={styles.corps}>
        <LienRetour vers={`/${profil.id}/portefeuille`}>Portefeuille</LienRetour>
        <div className={styles.titre}>
          <p className="t-etiquette c-500">Pacte vécu</p>
          <h1 className="t-h1">Revivez {resultat.joursMax} jours de marché</h1>
          <p className="t-corps c-700">
            {seuilDeclare !== undefined
              ? `Votre Pacte fixe votre pire baisse tolérée à ${seuilTexte(seuilDeclare)}, mais ce chiffre est une hypothèse. `
              : ''}
            Mesurons-la : voici de vrais jours de baisse, en dollars, sans la suite. Répondez comme si c’était votre argent.
          </p>
        </div>

        {question && (
          <>
            <div className={styles.progression}>
              <span className={styles.points} aria-hidden="true">
                {Array.from({ length: resultat.joursMax }, (_, i) => (
                  <span key={i} className={`${styles.point} ${i < joursRepondus ? styles.pointFait : ''} ${i === joursRepondus && question.type === 'baisse' ? styles.pointCourant : ''}`} />
                ))}
              </span>
              <span className="t-petit c-500">
                {question.type === 'baisse'
                  ? `Jour ${joursRepondus + 1} sur ${resultat.joursMax} au plus`
                  : 'Dernières questions'}
              </span>
            </div>
            <Question key={question.id} question={question} onRepondre={repondre} />
            <div className={styles.aide}>
              {Object.keys(reponses).length > 0 && (
                <Bouton variante="tertiaire" compact fleche={false} onClick={recommencer}>Recommencer</Bouton>
              )}
              {demo && (
                <Bouton variante="tertiaire" compact fleche={false} onClick={() => definirCalibrage({ reponses: demo.reponses, date: demo.date })}>
                  Utiliser les réponses de démonstration
                </Bouton>
              )}
              {demo && <Provenance type="Fictif" />}
            </div>
          </>
        )}

        {!question && (
          <section className={styles.resultat} aria-labelledby="titre-resultat" role="status">
            <h2 className="t-panneau" id="titre-resultat">Votre limite mesurée</h2>
            {resultat.seuil !== null ? (
              <p className={styles.seuil}>
                <span className="t-affiche">{pourcent(resultat.seuil)}</span>
                <span className="t-corps c-700">
                  de pire baisse tolérée{seuilDeclare !== undefined ? `, au lieu de ${seuilTexte(seuilDeclare)} supposé par l’équipe` : ''}.
                </span>
              </p>
            ) : (
              <p className="t-corps">
                Vous vendez dès la première baisse ({resultat.refusee !== null ? pourcent(resultat.refusee) : '—'}) : votre limite est
                plus stricte que ce que nous pouvons mesurer. Votre Pacte garde son seuil.
              </p>
            )}
            <ul className={styles.recap}>
              {resultat.jours.map(({ question: q, reponse }) => (
                <li key={q.id} className={styles.ligneRecap}>
                  <span className="t-trace c-500">{date(q.date_jour)}</span>
                  <span className="t-petit">{q.serie}</span>
                  <span className="t-tableau">{pourcent(q.baisse)}</span>
                  <span className={`t-petit-fort ${reponse === RESTE ? '' : styles.baisse}`}>{REPONSES_COURTES[reponse] ?? reponse}</span>
                </li>
              ))}
              {Object.entries(reponses).filter(([id]) => !id.startsWith('baisse_')).map(([id, reponse]) => (
                <li key={id} className={styles.ligneRecap}>
                  <span className="t-trace c-500">{id === 'capacite' ? 'Capacité' : id === 'crypto' ? 'Crypto' : 'Valeurs'}</span>
                  <span className="t-petit" />
                  <span />
                  <span className="t-petit-fort">{REPONSES_COURTES[reponse] ?? reponse}</span>
                </li>
              ))}
            </ul>
            <p className={styles.provenance}>
              <Provenance type={reponsesDemo ? 'Fictif' : 'Fait'} />
              <span className="t-petit c-500">
                {reponsesDemo ? 'Réponses de démonstration du profil fictif. ' : ''}Jours réels de marché : {donnees.source}. Le Tribunal citera ces réponses comme une pièce.
              </span>
            </p>
            <p className="t-petit c-500">{donnees.limites}</p>
            <div className={styles.aide}>
              <Bouton variante="primaire" vers={`/${profil.id}/portefeuille`}>Retour au portefeuille</Bouton>
              <Bouton variante="tertiaire" compact fleche={false} onClick={recommencer}>Recommencer</Bouton>
              {demo && !reponsesDemo && (
                <Bouton variante="tertiaire" compact fleche={false} onClick={() => definirCalibrage({ reponses: demo.reponses, date: demo.date })}>
                  Utiliser les réponses de démonstration
                </Bouton>
              )}
            </div>
          </section>
        )}
      </div>
    </Gabarit>
  );
}
