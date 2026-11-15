/** Écran d'entrée : choisir un profil de démonstration (annexe C.1). */
import { useNavigate } from 'react-router-dom';
import { configUi, idsProfils, libelleProfilRisque, profil as profilDe } from '../api/donnees';
import { Bouton } from '../components/Bouton';
import { Provenance } from '../components/Etiquettes';
import { Gabarit, useTitre } from '../components/Gabarit';
import { date, horizon } from '../lib/format';
import styles from './Entree.module.css';

export function Entree() {
  useTitre('Choisir un profil');
  const navigate = useNavigate();
  const profils = idsProfils().map((id) => profilDe(id)!);
  const debut = profils[0]?.debut;
  const fin = profils[0]?.fin;

  return (
    <Gabarit>
      <div className={styles.corps}>
        <div className={styles.titre}>
          <p className="t-etiquette c-500">Démonstration</p>
          <h1 className="t-h1">Avec quel profil voulez-vous explorer Astrée ?</h1>
          <p className={`t-corps c-700 ${styles.sousTitre}`}>
            Chaque profil a son portefeuille, son Pacte et une décision à soumettre au Tribunal. Vous pourrez changer de
            profil à tout moment depuis le menu en haut à droite.
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
                    <p className="t-petit c-700">Décision à tester</p>
                    <p className="t-corps-fort">{config.decisionATester}</p>
                    {config.question && <p className="t-citation c-700">{config.question}</p>}
                  </div>
                )}
                <Bouton variante="secondaire" fleche className={styles.entrer} onClick={(e) => { e.stopPropagation(); entrer(); }}>
                  Entrer comme {p.nom}
                </Bouton>
              </li>
            );
          })}
        </ul>

        <p className={`t-petit c-700 ${styles.pied}`}>
          <Provenance type="Fictif" />
          <span>
            Profils fictifs tirés de l'énoncé PolyFinances 2026. Portefeuilles simulés sur des prix réels
            {debut && fin ? ` du ${date(debut)} au ${date(fin)}.` : '.'}
          </span>
        </p>
      </div>
    </Gabarit>
  );
}
