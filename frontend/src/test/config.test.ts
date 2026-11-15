import { MESSAGE_TRIBUNAL_OCCUPE, lireErreur } from '../api/config';

const json = (statut: number, corps: unknown) =>
  new Response(JSON.stringify(corps), { status: statut, headers: { 'content-type': 'application/json' } });

describe('lireErreur', () => {
  it('429 de la Lambda (limite de débit, #136) : son message, qui donne le seuil', async () => {
    const reponse = json(429, { erreur: 'Trop de procès lancés depuis votre adresse : 3 par minute au plus. Réessayez dans une minute.' });
    expect(await lireErreur(reponse)).toContain('3 par minute au plus');
  });

  it('429 d’AWS (deux procès déjà en cours) : le message générique cite aussi la limite par minute', async () => {
    const message = await lireErreur(json(429, { Message: 'Rate Exceeded.' }));
    expect(message).toBe(MESSAGE_TRIBUNAL_OCCUPE);
    expect(message).toContain('deux procès au plus en même temps');
    expect(message).toContain('nombre limité de procès');
  });

  it('autre erreur : le champ « erreur », sinon le statut HTTP', async () => {
    expect(await lireErreur(json(404, { erreur: 'Aucun procès archivé' }))).toBe('Aucun procès archivé');
    expect(await lireErreur(new Response('<html>', { status: 502 }))).toBe('Le Tribunal a répondu 502');
  });
});
