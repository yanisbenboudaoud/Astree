/** Écran d'entrée : choisir un profil de démonstration (annexe C.1). */
import { Link, useNavigate } from 'react-router-dom';
import { configUi, idsProfils, libelleProfilRisque, profil as profilDe, profilsCrees } from '../api/donnees';
import { QUESTIONS } from '../api/questionnaire';
import { Bouton } from '../components/Bouton';
import { Provenance } from '../components/Etiquettes';
import { Gabarit, useTitre } from '../components/Gabarit';
import { date, horizon } from '../lib/format';
import styles from './Entree.module.css';

export function Entree() {
  useTitre('Choisir un profil');
  const navigate = useNavigate();
  const profils = idsProfils().map((id) => profilDe(id)!);
  const crees = profilsCrees();
  const debut = profils[0]?.debut;
  const fin = profils[0]?.fin;

  return (
    <Gabarit>
      <div className={styles.corps}>
        <div className={styles.titre}>
          <h1 className="t-h1">Testez une décision d'investissement avant de la prendre.</h1>
          <p className={`t-corps c-500 ${styles.sousTitre}`}>
            Un Procureur et un Avocat en débattent face à vos règles. Vous rendez le verdict.
          </p>
        </div>

        <ul className={styles.cartes}>
          {profils.map((p) => {
            const config = configUi(p.id);
            const entrer = () => navigate(`/${p.id}/portefeuille`);
            return (
              <li key={p.id} className={styles.carte} onClick={entrer}>
                <div className={styles.identite}>
                  <span className={styles.initiale} aria-hidden="true">{p.nom.charAt(0)}</span>
                  <div>
                    <h2 className="t-h2">{p.nom}</h2>
                    <p className="t-petit c-500">
                      {[p.age ? `${p.age} ans` : null, p.metier?.toLowerCase()].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                </div>
                <dl className={styles.caracteristiques}>
                  <div>
                    <dt className="t-petit c-700">Profil de risque</dt>
                    <dd className="t-petit-fort">{libelleProfilRisque(p.profilRisque)}</dd>
                  </div>
                  <div>
                    <dt className="t-petit c-700">Horizon</dt>
                    <dd className="t-petit-fort">{horizon(p.horizonAns)}</dd>
                  </div>
                </dl>
                {config.decisionATester && (
                  <div className={styles.decision}>
                    <p className="t-petit c-500">Décision à tester</p>
                    <p className="t-corps-fort">{config.decisionATester}</p>
                  </div>
                )}
                <Bouton variante="secondaire" fleche className={styles.entrer} onClick={(e) => { e.stopPropagation(); entrer(); }}>
                  Entrer comme {p.nom}
                </Bouton>
              </li>
            );
          })}
        </ul>

        <section className={styles.construire} aria-labelledby="titre-construire">
          <div className={styles.texteConstruire}>
            <h2 className="t-h2" id="titre-construire">Votre propre Pacte</h2>
            <p className="t-corps c-500">{QUESTIONS.length} questions, environ 5 minutes.</p>
            {crees.length > 0 && (
              <p className="t-petit c-700">
                Reprendre :{' '}
                {crees.map((p, i) => (
                  <span key={p.id}>{i > 0 && ', '}<Link to={`/${p.id}/portefeuille`}>{p.nom}</Link></span>
                ))}
              </p>
            )}
          </div>
          <Bouton variante="primaire" vers="/construire">Construire mon Pacte</Bouton>
        </section>

        <p className={`t-petit c-700 ${styles.pied}`}>
          <Provenance type="Fictif" />
          <span>
            Profils fictifs, prix réels{debut && fin ? ` du ${date(debut)} au ${date(fin)}` : ''}.
          </span>
        </p>
      </div>
    </Gabarit>
  );
}
