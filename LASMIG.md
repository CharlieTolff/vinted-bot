# Vinted-bevakaren

Söker på Vinted var tredje minut med dina sparade sökningar och skickar nya annonser till Telegram med bild, pris och länk.

## Hemsidan och Telegram
- `hemsida/index.html` är din alarm-sida. Där lägger du till alarm och ser alla träffar.
- Alla tre sidorna har samma meny högst upp: Alarm, Börsen och Bokföring.
- "⭐ Bästa kapen just nu" på alarm-sidan samlar kapen och träffarna med vinst från alla alarm. Träffarna kan sorteras
  (nyast, mest vinst, lägst pris) och döljas med ×, och de dolda kommer ihåg i webbläsaren.
- Alarm-sidan visar bara Sverige, Danmark, Finland och Polen, alltså länderna du kan köpa från med ett svenskt Vinted-konto.
- Telegram skickar bara **kap**: priset är högst ditt kap-pris, eller (utan kap-pris) högst hälften av vanliga priset för sökningen. Per alarm kan du välja "Bara kap", "Alla nya träffar" eller "Inga".
- `traffar.json` skapas automatiskt och är det hemsidan visar. Varje runda kollar boten några av annonserna på hemsidan och tar bort de som är sålda eller borttagna på Vinted.
- På GitHub körs allt var 5:e minut av `.github/workflows/bevaka.yml`.

## Märkesbörsen
- `hemsida/bors.html` är märkesbörsen: hur märkena i dina alarm går på Vinted, Tradera och Plick, i Avanza-stil.
  Du ser varje märkes andel av marknaden i en kategori (t.ex. koftor), hur andelen och priset gått upp eller ner,
  och kan dra över diagrammet för att mäta förändringen mellan två dagar.
- `marknad.py` mäter efter varje botrunda en liten stund (högst 50 sekunder och några få frågor till Vinted), så
  varje märke och kategori mäts ungefär en gång per dygn. Resultatet sparas i `bors.json`.
- Vinted och Plick visar utbudet (annonser ute nu, begärt pris). Tradera visar det som faktiskt sålts och slutpriset,
  vecka för vecka, så där syns efterfrågan.
- Kategorierna står överst i `marknad.py` (`KATEGORIER`). Märkena tas från alarmen automatiskt.
- "Bästa köplägena" visar dina märken där Tradera-slutpriset ligger mest över de billiga Vinted-annonserna, och
  "Nya märken att bevaka" märken som säljer mycket på Tradera men saknas i dina alarm. "+ Alarm" öppnar ett förifyllt alarm.
- "Sålda 24 h" är hur många av märket som sålts senaste dygnet. På Vinted gås alla märkets annonser i kategorin igenom ungefär en gång per dygn (upp till 960), och de som försvunnit sedan förra gången räknas som sålda (några kan vara borttagna). Tradera räknas som snittet per dygn senaste veckan. Plick visar inte sålda och räknas inte.
- Säljpriset på alarmen räknas per märke när det finns minst 5 annonser av märket, så olika märken i samma alarm får olika pris.
- "Bästa kapen" visar bara kap och träffar med minst 100 kr vinst (högst 60).
- Efter varje mätning skriver `marknad.py` de största märkena per kategori i Actions-loggen.

## Bokföringen
- `hemsida/bokforing.html` visar bokföringen från Lager-fliken i arket "Valto Resell": total vinst, utvecklingen över tid,
  vinst/omsättning per vecka, månad, 3 månader och år, sålda varor, märken, kategorier, plattformar och lagret.
- Hemsidan är öppen för alla som har länken, så bokföringen är krypterad och låses upp med ett lösenord i webbläsaren.
- `bokforing.py` hämtar arket och krypterar det vid varje botrunda. Den behöver två GitHub-secrets:
  `BOKFORING_ARK` (länken till arket, som måste vara delat med "alla som har länken") och `BOKFORING_LOSEN` (lösenordet).
  Saknas de visas den sparade kopian `hemsida/bokforing.enc`.
- Hemsidan visar bara kläderna från botten och det du säljer nu. Gamla Japan-köp (Mercari, ZenMarket, Amazon) och
  golf, småläder och klockor räknas inte där, men finns kvar i arket. Det styrs av `GAMLA_KALLOR` och `GAMLA_KATEGORIER`
  i `hemsida/bokforing.html`. Typ = Privat räknas inte med. En såld vara räknas till veckan/månaden den såldes, och inköp till när de köptes.
- Månadsmålet sätts på sidan och sparas i webbläsaren. "Varor som fastnat" är varor som legat minst 21 dagar
  (`FAST_DAGAR`), med ett prisförslag från börsen. "Vinst per alarm" använder kolumnen `Alarm` i arket om den finns,
  annars det alarm som bevakar varans märke.

## Filer
- `vinted_bot.py` – själva programmet (behöver bara Python 3, inget att installera).
- `sokningar.json` – dina bevakningar. Ändra här, ändringen gäller från nästa runda.
- `installningar.json` – Telegram-token, chat-id och hur ofta det ska sökas.
- `sedda.json` – skapas automatiskt och minns vilka annonser du redan fått.
- `minne.json` – skapas automatiskt och minns priser, säljare och märken.

## En bevakning
```json
{
  "namn": "Nudie jeans under 200 kr",
  "sokord": "nudie jeans",
  "kon": "herr",
  "kategorier": ["klader"],
  "lander": ["SE", "DK", "FI"],
  "maxpris": 200,
  "minpris": 50,
  "marke": "Nudie",
  "storlekar": ["W30", "W31", "M"],
  "skick": ["Ny med prislapp", "Ny utan prislapp", "Mycket bra"],
  "uteslut": ["t-shirt", "jacka"],
  "kappris": 120,
  "frakt": 60,
  "min_betyg": 4.5,
  "telegram": "kap",
  "aktiv": true
}
```
Allt utom `namn` och `sokord` kan lämnas bort. Tom lista betyder "alla". Enklast är att ändra på hemsidan.

- `kon` och `kategorier`: "herr" eller "dam", och kategorierna klader, skor, accessoarer (och vaskor för dam).
  Botten använder Vinteds egna filter, så du får bara rätt sorts saker.
- `sokord` och `marke` kan vara en text eller en lista, t.ex. `["skjorta", "oxford"]`. Ett sökord räcker för träff, och flera märken bevakas samtidigt.
- `marke`: botten slår upp märket hos Vinted och söker bara på det märket.
- `storlekar`: måste stämma exakt, så "S" träffar inte "XS".
- `maste`: fraser som måste stå i titeln, t.ex. `["regular alf"]` för en viss modell. Alla ord i frasen måste finnas, och en av fraserna räcker.
- `farger`: Vinteds färgfilter, t.ex. `["Svart", "Marinblå"]`. Tomt = alla färger. Färger som finns: Svart, Grå, Vit, Crèmefärgad, Beige, Aprikos, Orange, Korall, Röd, Vinröd, Rosa, Ros, Lila, Syrenlila, Ljusblå, Blå, Marinblå, Turkos, Mint, Grön, Mörkgrön, Khaki, Brun, Senapsgul, Gul, Silver, Guld, Flerfärgad, Genomskinlig.
- `skick`: används också som Vinted-filter. Skick som finns: Ny med prislapp, Ny utan prislapp, Mycket bra, Bra, Tillfredsställande.
- `lander`: vilka länder säljaren ska bo i. På svenska Vinted kan du köpa från SE (Sverige), DK (Danmark), FI (Finland) och PL (Polen).
  Lägg till FR (Frankrike), IT (Italien), ES (Spanien) eller DE (Tyskland) så söker boten även på landets egen Vinted,
  ett land per runda i tur och ordning. Där köper du via en köptjänst (t.ex. Proxy Orders hos French Forwarders),
  så att du inte behöver ett eget konto i landet. Priset räknas om från euro till kronor med dagens kurs.
- `utlandskostnad`: vad köptjänsten och frakten hem kostar per plagg från utlandet (standard 400 kr). Maxpris, kap-pris och
  vinst räknas för utländska annonser på vad plagget kostar hemma i Sverige, alltså pris + avgift + `utlandskostnad`.
- `sokord_utland`: sökord att använda utomlands, t.ex. modellnamn eller franska ord. Tomt = samma som `sokord`. Högst 4 används.
- `min_betyg`: säljare med lägre snittbetyg (stjärnor) hoppas över. Säljare utan omdömen är okej. 0 stänger av.
- Säljpriset uppskattas automatiskt: botten söker (var 6:e timme) på samma sak utan prisgräns och tar priset där
  40 % av liknande annonser är billigare, justerat för skicket. Vinsten = säljpris − (pris + Vinteds avgift + `frakt`).
- Efterfrågan (låg/medel/hög) räknas på hur många som brukar gilla liknande annonser.
- Vanligt pris räknas på alarmets träffar de senaste 30 dagarna (minst 8 st), och kap räknas mot det.

Vill du ha andra filter från Vinted (färg osv.)? Gör sökningen på vinted.se, kopiera länken och skriv
`"url": "https://www.vinted.se/catalog?..."` i stället för `sokord`.

## Skaffa en Telegram-bot (5 min)
1. Öppna Telegram och sök på **@BotFather**.
2. Skriv `/newbot`, välj ett namn och ett användarnamn som slutar på `bot`.
3. Du får en **token** (ser ut som `123456:ABC-...`). Lägg in den i `installningar.json`.
4. Öppna din nya bot i Telegram och skicka "hej" till den.
5. Kör `python3 vinted_bot.py --hitta-chat-id` och lägg in siffran som `telegram_chat_id`.

## Köra
- `python3 vinted_bot.py --test` skickar de 3 senaste träffarna, så du ser att notiserna funkar.
- `python3 vinted_bot.py` bevakar tills du stänger av den.
- Första gången sparas alla nuvarande annonser som "sedda", så du bara får helt nya.

## Bildkollen

En bildmodell tittar på bilden i varje ny träff och sorterar bort fel plagg (till exempel en sweatshirt i alarmet för stickade hoodies), så att vinsten räknas på rätt saker. Den granskar också annonserna som säljpriset räknas på. Gratis: CLIP körs direkt på GitHub och jämför bilden med alarmets `bild_ja` och `bild_nej` i sokningar.json (alarm utan dem granskas inte). Finns hemligheten `ANTHROPIC_API_KEY` används Claude i stället. Högst 40 bilder per runda med CLIP (15 med Claude, `BILD_PER_RUNDA`), och varje annons granskas bara en gång.
