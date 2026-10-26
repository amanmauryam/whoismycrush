# Admin guide (single admin)

Yeh guide WhoIsMyCrush ke **ekmatra admin** ke liye hai. Aap hi manager aur final
decision maker ho. Koi doosra admin account nahi hai. Har important kaam aap
khud karoge.

**Real admin address:**

<https://whoismycrush.com/802134admin/>

Sirf yahi real address use karein. Purane notes ka koi doosra address kaam nahi
karega.

**Sabse important rule:** student ko match tabhi dikhega jab **aap approve
karenge**. Approve ka matlab hai aapki final "haan". Approve se pehle dono
students ki details check karna zaroori hai.

**Privacy rule:** kisi student ko kabhi na batayein ki usne kisko chuna, kisi ne
use kya likha, ya uski list mein kya priority thi. Support reply mein bhi nahi.

---

## 1. Simple words (Hinglish)

Technical word use hone se pehle yahan uska simple matlab diya hai.

| Word | Simple Hinglish meaning |
| --- | --- |
| Admin | Website ka manager. Control room se saara data dekha aur manage kiya jata hai. |
| URL | Web address, jaise `https://whoismycrush.com/802134admin/`. |
| Django admin | Website ka control room. Yahan se students, entries, matches aur reports manage hoti hain. |
| Server | Computer jo website ko live rakhta hai. |
| Hosting | Company jo website ka server chalati hai. |
| Live site | Asli website, jise students use karte hain. |
| Database | Data rakhne ki jagah. Isme har student, entry aur match ki ek line hoti hai. |
| Record / row | List ki ek line. Example: ek student ka profile ya ek match proposal. |
| Field / box | Form ka ek khaana, jaise Name, Roll number ya Status. |
| Status | Kisi record ki current condition. Example: Pending, Approved, Rejected. |
| Filter | List ko chhota karne ka option. Example: sirf "Pending" wale records dikhana. |
| Action | List ke upar ka dropdown. Selected records par ek saath kaam karne ke liye. |
| Approve | Final "haan". Match approve karne par students ko alert jata hai. |
| Reject | "Nahi". Match reject karne par kisi ko alert nahi jata. |
| Defer | "Abhi decide nahi". Baad mein proof milne par phir dekhna. |
| Roll number | College ka student ID. |
| Priority | Student ki list mein 1 se 3 ka internal order. Student ko kabhi na dikhe. |
| Identity candidate | Ek possible registered student. Yeh match nahi hai, sirf pehchaan ka sujhav hai. |
| Potential match | Ek match proposal. Yeh abhi match nahi hai; aapki approval ke baad match banta hai. |
| Mutual match | Dono students ne ek doosre ko chuna, aur aapne approve kiya. |
| Backup | Safety copy. Kuch bada change karne se pehle purani copy save karna. |
| Command | Terminal mein diya gaya chhota instruction. Terminal ek black command window hoti hai. |
| Migration | Database ka structure update karne ka step. |
| Deploy | Naya code website par live karna. |
| SMTP | Email bhejne ka system. |
| Environment setting | Server ki settings, jo code ke bahar ek settings file mein hoti hain. |
| Slug | Web address ka last part. Example: `pro-tips/first-crush/` mein `first-crush` slug hai. |
| Reveal | Dono students ki permission ke baad ek doosre ka naam kholna. |
| In-app alert | Website ke andar dikhne wala notification. |
| Audit / audit trail | Kaun, kab, kya change kiya, iska permanent record. |
| Log | System ka record, jahan errors aur events likhe jate hain. |
| Secret key | Website ki security key. Isse badalne par purane logins band ho jate hain. |
| Rate limit | Ek user ko bahut zyada requests bhejne se rokna. |
| HTML | Web page banane ka code. |
| UTC | Duniya ka standard time; India ka time UTC se 5 ghante 30 minute aage hai. |
| WebP | Halka image format, jo website ko fast rakhta hai. |
| SEO | Google jaise search engine mein page ko sahi dikhane ki setting. |
| Canonical URL | Batana ki isi content ka asli address kaun sa hai. |
| Sitemap | Search engine ke liye website ke pages ki list. |
| Robots file | Search engine ko batati hai kaun se page dekhne hain. |
| App password | Email app ke liye special password, normal account password nahi. |
| Test / staging server | Live site ki copy, jahan pehle change test karte hain. |
| Restore | Backup se purana data wapas laana. |
| Dependencies | Website ke saath kaam karne wale doosre software. |

---

## 2. Your login and access

Aapke paas sirf **ek admin login** hona chahiye. Yeh login sab kuch kar sakta
hai, isliye ise sambhal kar rakhein.

### Login

1. Browser mein yeh real address kholein:
   <https://whoismycrush.com/802134admin/>
2. Username aur password daalein.
3. Login ke baad aapko control room ka home page dikhega.

### Rules

- Password kisi ke saath share na karein. Notepad, chat ya email mein save na
  karein.
- Public computer par kaam ke baad **Log out** karein.
- Doosra admin account na banayein. Aap hi ek admin ho.
- Agar password bhool jayein, server par yeh command chalayein:
  `python manage.py changepassword your-admin-username`
  Isme `your-admin-username` ki jagah apna username likhein. Command ka matlab:
  "mere admin account ka password badal do."
- Agar login page na khule, pehle URL check karein. URL mein `/802134admin/`
  hona chahiye.

---

## 3. First-time setup

Yeh steps naye server par ek baar chalte hain. Command ka matlab simple Hinglish
mein neeche diya hai.

```powershell
python manage.py migrate
python manage.py seed_posts
python manage.py seed_colleges
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check_email --to noreply@whoismycrush.com
```

- `migrate` = database ka structure banayein ya update karein.
- `seed_posts` = shuruaat ke Pro Tips articles daalein. Isse dobara chalane par
  purane articles kharab nahi hote.
- `seed_colleges` = kuch starter colleges ki list daalein. Isse dobara chalana
  safe hai.
- `createsuperuser` = admin account banayein. `superuser` ka simple matlab hai
  "poora access wala admin".
- `collectstatic` = website ke design files, images aur editor files server par
  copy karein.
- `check_email` = test email bhejkar check karein ki email system kaam kar raha
  hai. Test ke liye apna working email daalein.

**Sirf testing ke liye commands:** `seed_demo` fake students banata hai, aur
`seed_match` ek demo match approve karke asli match alerts bhej deta hai. Live
site par yeh commands kabhi na chalayein.

### Important server settings

Yeh settings server ki settings file (environment file) mein hoti hain. Agar aap
khud server manage nahi karte, hosting support ko yeh values dein.

| Setting | Correct live value | Simple matlab |
| --- | --- | --- |
| `SITE_URL` | `https://whoismycrush.com` | Emails aur website links mein yahi address use hoga. |
| `ALLOWED_HOSTS` | `whoismycrush.com` | Sirf isi website ko server par kaam karne dena. |
| `DEBUG` | `False` | Live site par errors ki detailed screen band rakhna. |
| `EMAIL_VERIFICATION_REQUIRED` | `True` ya `False` | `True` ka matlab student ko email confirm karna hoga. |
| `MATCH_EMAILS_ENABLED` | `True` | Match approve hone par email bhejni hai ya nahi. Website ke andar ka alert phir bhi aayega. |

Poori live-site checklist: `docs/deployment.md`.

---

## 4. Daily routine (15-30 minutes)

Live site par har din, weekend bhi, yeh order follow karein. Queue ka matlab hai
"jin cheezon ka aapko intezaar hai". Queue purani na chhodein, warna students ko
match late milega.

### 4.1 Pehle unclear identities solve karein

**Kab:** roz, aur match proposals approve karne se pehle.

**Kyun:** agar student ki pehchaan clear nahi hai, to match safe tarike se
approve nahi ho sakta.

**Real page:**
<https://whoismycrush.com/802134admin/campus/identitycandidate/>

1. Page kholein.
2. Right side ke **Filter** se **Status** = **Candidate** ya **Needs review**
   chunein.
3. Ek row kholein. Usme likha hoga:
   - student ne kya naam type kiya,
   - system ko kaun sa registered student milta jaisa lag raha hai,
   - naam kitna milta hai,
   - course, year aur section kitna match karta hai.
4. Details ko dhyan se compare karein. Sirf naam dekhkar confirm na karein.
5. Agar ek hi student saaf taur par sahi hai, to row ke left wala checkbox
   tick karein. Phir upar **Action** dropdown se
   **Confirm selected identity candidates** chunein aur **Go** dabayein.
6. Agar candidate galat hai, to **Reject selected identity candidates** chunein.
7. Agar external proof chahiye, to **Defer selected identity candidates** chunein.
8. Agar kisi bhi student ko safe tarike se identify nahi kar sakte, to
   **Crush entries** page kholein:
   <https://whoismycrush.com/802134admin/campus/crushentry/>
   Wahan entry select karein aur **Mark identity unresolvable (keeps original
   entry)** action chunein. Isse original entry private rehti hai aur ghalat
   match nahi banta.
9. Baad mein identity dobara check karni ho to **Reopen identity resolution**
   action use karein.

Is step par kisi student ko koi alert nahi jata. Identity confirm karna sirf
"yeh banda kaun hai" clear karta hai. Match tabhi banta hai jab dono taraf ki
entry ho aur aap match approve karein.

#### Proper example: missing roll number

Yeh example fictional hai. Asli student ki details docs ya ticket mein na likhein.

1. Aman ne crush entry mein **Riya Sharmaa** likha, roll number khali chhoda, aur
   **ABC College, BCA, Year 2, Section A** chuna.
2. Admin ko candidate milta hai: **Riya Sharma, roll 23BCA102, ABC College, BCA,
   Year 2, Section A**.
3. Naam bilkul same nahi hai aur roll number bhi student ne nahi diya, isliye
   system ne apne aap link nahi kiya. Yeh sahi behaviour hai.
4. Aap college ki class list se check karte ho ki yeh wahi Riya hai.
5. Identity candidate page par us row ka checkbox tick karein, phir
   **Confirm selected identity candidates** action chunein.
6. Riya ne bhi Aman ke liye entry ki hai, jisme Aman ka roll number **23BCA101**
   sahi hai. Woh side system khud confirm kar leta hai.
7. Ab match proposal page par yeh jodi dikhegi. Aap dono ki details check karke
   approve karein.
8. Dono students ko sirf ek simple alert jayega: "someone you chose also chose
   you." Riya ke candidate hone ki detail, roll number ya evidence Aman ko kabhi
   na batayein.

Agar candidate galat nikle to reject karein. Agar do log possible hain to defer
karein. Agar koi bhi safe tarike se identify na ho to **Mark unresolvable** karein.
In teeno mein se kisi bhi case mein match ya alert nahi banta.

### 4.2 Match proposals approve karein

**Kab:** roz, aur kisi event ya promotion se pehle.

**Kyun:** proposal ka matlab "shayad match hai" hota hai. Match tabhi banta hai
jab aap approve karte ho. Late approval se feature toota hua lagta hai.

**Real page:**
<https://whoismycrush.com/802134admin/campus/potentialmatch/>

1. Filter se **Status** = **Pending Verification** chunein.
2. Ek row kholein. Har row ek taraf ki entry hai. Sahi jodi mein do rows hoti
   hain, ek har student ki taraf se.
3. Column **Is reciprocal** check karein. Agar **No** hai to yeh ek taraf ki
   entry hai. Aise row ko approve na karein; system use skip kar dega.
4. Neeche diya checklist poora check karein.
5. Ek jodi ki sirf **ek row** select karein. Dono rows select karne ki zaroorat
   nahi. Ek row approve karne se poori jodi approve hoti hai.
6. **Action** dropdown se
   **Approve selected (creates mutual crush + notifies)** chunein aur **Go**
   dabayein.
7. Page par confirmation message dekhein. Agar likha ho "skipped", to reason
   samajhne ke liye row phir kholein. Aksar identity resolve nahi hoti ya doosri
   taraf ki entry missing hoti hai.
8. Agar match galat hai to **Reject selected (nobody is notified)** chunein.
   Isse poori jodi band ho jati hai aur kisi ko alert nahi jata.

**Approve karne se pehle checklist:**

- [ ] Dono students **same college** ke hain.
- [ ] Dono entries registered students se sahi linked hain.
- [ ] Dono taraf ki entry maujood hai. Ek taraf ki entry approve nahi hoti.
- [ ] Type kiya hua naam usi student ka lagta hai. Spelling alag ho sakti hai,
      lekin naam ya surname bilkul alag nahi hona chahiye.
- [ ] Course, year aur section mein koi bada contradiction nahi hai.
- [ ] Dono accounts active hain.
- [ ] Dono ke beech koi block nahi hai.
- [ ] Koi duplicate profile ya duplicate college involved nahi hai.

Agar kuch bhi confusing ho to approve na karein. Reject karne se match
permanently band hota hai. Baad mein naya proposal nahi banega, isliye reject
sirf tab karein jab aapko pakka ho.

**Approve karne par kya hota hai:**

- Ek real mutual match banta hai.
- Dono students ko ek simple in-app alert jata hai.
- Email bhi ja sakta hai, agar setting on hai.
- Kisi ka naam, roll number ya "kisne pehle chuna" reveal nahi hota.
- Naam tabhi khulta hai jab dono students reveal ke liye haan kahein.

**Reject karne par kya hota hai:**

- Poori jodi reject ho jati hai.
- Kisi student ko koi alert nahi jata.
- Wahi jodi dobara apne aap propose nahi hoti.

Admin list mein status ko haath se **Approved** na karein. Sirf approve/reject
actions use karein. Isse notification, audit aur duplicate safety sahi rehti hai.

### 4.3 Reports dekhein

**Kab:** roz. Harassment ya safety report ho to turant.

**Kyun:** report student ki safety ka main rasta hai. Website promise karti hai
ki report review hogi.

**Real page:**
<https://whoismycrush.com/802134admin/campus/report/?status__exact=open>

1. Report kholein aur reason aur detail padhein.
2. Reporter ki identity confidential rakhein.
3. Reported student ka profile aur recent activity dekhein.
4. Decision lein:
   - Galat naam ya typo: entry theek karein ya inactive karein.
   - Fake profile: us user ka account deactivate karein.
   - Harassment: account deactivate karein; zaroorat ho to block lagayein;
     evidence sambhal kar rakhein.
   - Duplicate profile: duplicate account band karein, sahi profile rakhein.
   - Koi violation nahi: dismiss karein.
5. **Mark reviewed** ya **Dismiss** action use karein.
6. Account par action liya ho to apne incident record mein likhein: kab, kis
   account par, aur kyun.

**Block ka important rule:** admin ke Block page se sirf ek block row banti hai.
Student ke apne block button jaisa cleanup apne aap nahi hota. Isliye normal
block ke liye student-facing button use karein. Admin se block lagana zaroori ho
to related pending proposals aur matches bhi manually check karein.

### 4.4 Contact messages dekhein

Public contact form ke messages admin control room mein save hote hain.

**Real page:**
<https://whoismycrush.com/802134admin/contact/contactmessage/>

1. Filter se **Status** = **Pending** chunein.
2. Message kholein aur padhein.
3. Official support email se reply karein, apne personal email se nahi.
4. Reply ke baad **Mark selected messages as resolved** action chunein.

Kisi doosre student ki private information reply mein na likhein.

### 4.5 Email verification requests

**Kab:** jab student kahe "verification link nahi aaya", ya email verification
on karne se pehle.

**Real page:**
<https://whoismycrush.com/802134admin/accounts/emailverification/>

1. Pehle student ko website ke banner se **Resend verification** karne ko kahein.
2. Page par student ka email ya username search karein.
3. Confirm karein ki aap usi account ke owner se baat kar rahe hain. Official
   account email par reply karein.
4. Row select karein aur **Mark selected emails verified** action chunein. Ya row
   kholein aur verification date/time set karein.

Do alag cheezein confuse na karein:

| Field | Simple matlab | Asar |
| --- | --- | --- |
| Email verification date | Account ka email confirm hua | Banner hat jata hai; email verification on ho to login ke liye zaroori. |
| Profile verified tick | Profile par trust badge | Sirf dikhane aur review ke liye. Yeh match ko block nahi karta. |

---

## 5. Weekly routine

### 5.1 New student profiles check karein

**Real page:**
<https://whoismycrush.com/802134admin/campus/studentprofile/>

- Filter se **Is verified = No**, college aur recent signups dekhein.
- Naam, roll number format, duplicate naam aur fake profiles check karein.
- Sirf pakka hone par **Is verified** tick karein. Yeh ek trust badge hai, lock
  nahi.
- Match theek karne ke liye roll number ya naam edit na karein. Isse purani
  entries aur proposals galat ho sakti hain.
- Ek hi student ke do profiles hon to duplicate account deactivate karein.
  History ko blindly delete na karein.

### 5.2 Colleges clean rakhein

**Real page:**
<https://whoismycrush.com/802134admin/campus/college/>

- Ek asli college ke liye ek hi row rakhein. Duplicate rows matching pool ko
  todti hain.
- College band karna ho to **Is active** untick karein. Delete na karein.
- `slug` (URL ka last part) share hone ke baad change na karein. Warna college
  page aur join page ke links toot jayenge.
- Purane students aur entries hone par college delete nahi hota. Isliye inactive
  karein.

### 5.3 College invite requests dekhein

**Real page:**
<https://whoismycrush.com/802134admin/campus/collegeinvite/>

Yahan students ki "mera college add karo" requests hoti hain. Status sirf
tracking ke liye hai; status badalne se kisi ko email nahi jata.

- Pending = abhi dekha nahi.
- Approved = college add ho gaya.
- Declined = college add nahi hoga.

Queue weekly clear karein, taaki demand ka sahi pata chale.

### 5.4 Pro Tips check karein

**Real page:**
<https://whoismycrush.com/802134admin/blog/post/>

- Drafts, future-dated posts aur scheduled posts dekhein. Future date wala post
  us time tak hidden rehta hai.
- **Featured** posts kam rakhein, sirf useful guides ke liye.
- Title, excerpt, cover image aur category proofread karein.
- Links aur images check karein.
- Purana ya galat post delete karne ke bajaye **Is published** untick karein.
  Legal ya security reason ho to hi delete karein.

### 5.5 Backup aur email check

- Database (data ki jagah) aur `MEDIA_ROOT` (uploaded images/files ki jagah) ka
  fresh backup check karein.
- Mail ya hosting change ke baad test email chalayein:
  `python manage.py check_email --to noreply@whoismycrush.com`
  Test ke liye apna working address use karna behtar hai.
- Email fail ho raha ho to email log dekhein. In-app alerts email fail hone par
  bhi save hote hain, isliye email outage chhup sakta hai.
- Setting change ke baad `python manage.py check` chalayein. Yeh command
  configuration ki galtiyan batati hai.

---

## 6. Monthly and quarterly routine

### Monthly

- **Matcher dobara chalayein** agar import, ek saath bahut profile edits, ya
  match miss hone ka shak ho:

  ```powershell
  python manage.py shell -c "from campus.services import reconcile_all_matches; print(reconcile_all_matches())"
  ```

  `shell` ka matlab: server ke andar chhota Python command chalana. Yeh command
  sirf naye proposals banata hai. Kisi ko approve ya notify nahi karta.

- **Tooti matches saaf karein** sirf backup ke baad, aur sirf jab reason pata
  ho:

  ```powershell
  python manage.py shell -c "from campus.services import prune_broken_matches; print(prune_broken_matches())"
  ```

  Yeh un match records ko delete karta hai jinka koi approved proposal nahi hai
  aur doosri taraf reject ho chuki hai. Notifications delete nahi hoti.

- `python manage.py test` chalayein. Yeh automatic test hai jo batata hai ki
  website ka main kaam toota nahi.
- `https://whoismycrush.com/sitemap.xml` aur
  `https://whoismycrush.com/robots.txt` khulkar check karein.
- Total numbers dekhein: kitne active students, kitne matches, kitni reports
  pending. Kisi ek student ki activity spy na karein.
- Apna admin password aur recovery email check karein. Sirf ek admin account
  rakhein.

### Quarterly

- Backup ko test server par restore karke check karein ki woh kaam karta hai.
  Bina test kiya backup sirf ek guess hai.
- Password aur secret keys badal kar naye banayein. Secret key badalne se sab
  users log out ho jate hain.
- Supporting software update karein. Pehle test server par, phir live site par.
- Purane articles, links aur screenshots check karein.

---

## 7. Admin pages reference

Har page ka real URL diya hai. `Model` ka matlab yahan "data ka section" hai.

### College

<https://whoismycrush.com/802134admin/campus/college/>

- **Kab:** naya college add karna ho, duplicate clean karna ho, ya college hide
  karna ho.
- **Kyun:** college matching ki hard limit hai. Do college ke students kabhi
  match nahi hote.
- **Karein:** naam, city aur state sahi rakhein. Share hone ke baad `slug` na
  badlein. Delete ke bajaye **Is active** untick karein.
- **Na karein:** do asli colleges ko similar dikhne par merge na karein.

### Student profile

<https://whoismycrush.com/802134admin/campus/studentprofile/>

- **Kab:** weekly check, report investigation ya duplicate profile.
- **Kyun:** matcher isi profile aur roll number par bharosa karta hai.
- **Karein:** campus rules se verify karein. Fake profile ka user account
  deactivate karein.
- **Na karein:** match banane ke liye naam ya roll number edit na karein.
  `Is verified` ko matching lock na samjhein; yeh sirf badge hai.

### Crush entry

<https://whoismycrush.com/802134admin/campus/crushentry/>

- **Kab:** match debug, wrong-person report, ya proposal audit.
- **Kyun:** yahan student ne jo naam type kiya woh save hota hai. Isme internal
  priority aur admin-only identity state bhi hoti hai.
- **Karein:** ambiguous identity ke liye identity candidate page use karein.
  Entry ko inactive sirf student request ya report par karein.
- **Na karein:** `priority`, candidate evidence ya resolved link ko expose na
  karein. Match banane ke liye entry edit na karein. Resolved fields haath se
  na badlein; admin actions use karein.

Priority 1 se 3 tak hoti hai. Yeh student ko kabhi na dikhe, na support reply
mein likhein.

### Identity candidate

<https://whoismycrush.com/802134admin/campus/identitycandidate/>

- **Kab:** roll number missing ya ambiguous ho, ek jaise naam hon, ya student
  apna campus ID theek kare.
- **Kyun:** yeh possible identity ka evidence hai. Yeh match nahi hai.
- **Karein:** candidate kholein, details compare karein, phir **Confirm**,
  **Reject** ya **Defer** action chunein.
- **Na karein:** sirf naam dekhkar confirm na karein. Har row khole bina ek saath
  confirm na karein. Candidate detail student ko na batayein.

Rejected aur deferred candidates apne aap dobara link nahi hote. Identity audit
log sirf padhne ke liye hai, matlab purani entries badli nahi ja sakti.

### Identity audit log

<https://whoismycrush.com/802134admin/campus/identityresolutionaudit/>

Yeh sirf padhne ke liye record hai. Isme dikhta hai kis entry par, kab, kis
admin ne kya action liya. Isse edit ya delete na karein.

### Potential match (match proposals)

<https://whoismycrush.com/802134admin/campus/potentialmatch/>

- **Kab:** daily review.
- **Kyun:** yeh "kisi ne naam type kiya" se "match announce hua" tak ka safe
  rasta hai.
- **Karein:** ek jodi ki ek row select karein, checklist check karein, phir
  **Approve selected** ya **Reject selected** action chunein.
- **Na karein:** status, approve karne wale ka naam ya linked match haath se na
  badlein. Unpaired row approve na karein. Bina check kiye ek saath approve na
  karein.

Confidence score (match ka score) sirf hint hai, proof nahi. Score naam, course,
year, section, department aur nickname se banta hai. High score ke baad bhi
aapko details check karni hongi. Course/year/section ka bada contradiction ho to
pair galat hai. Notification ek hi baar jata hai, chahe aap dobara approve karein.

### Mutual match (approved matches)

<https://whoismycrush.com/802134admin/campus/mutualmatch/>

- **Kab:** report ya block ke baad match band karna ho, ya approved match audit
  karna ho.
- **Kyun:** match sensitive hai; band karna soch samajh kar karein.
- **Karein:** **Close selected matches** action use karein. Yeh sirf status
  badalta hai aur kisi ko notify nahi karta.
- **Na karein:** Revealed status haath se set na karein. Yeh dono students ki
  permission ka rasta bypass kar deta hai. Match delete karke approval undo na
  karein; close karein aur reason record karein.

Status ka matlab:

- Mutual = approved match, abhi naam nahi khula.
- Reveal pending = ek student ne reveal maanga hai.
- Revealed = dono ne permission di, naam khul gaye.
- Closed = match band.

Reveal ki permission students dete hain, admin nahi.

### Report

<https://whoismycrush.com/802134admin/campus/report/>

- **Kab:** daily.
- **Kyun:** safety aur trust.
- **Karein:** investigate karein, action lein, phir **Mark reviewed** ya
  **Dismiss** karein.
- **Na karein:** reporter ki identity reported student ko na batayein. Bina
  padhe dismiss na karein.

### Block

<https://whoismycrush.com/802134admin/campus/block/>

- **Kab:** student normal block flow use na kar sake, ya investigation ke liye.
- **Kyun:** block do students ke beech matching band karta hai.
- **Karein:** normal block ke liye student-facing button use karein. Woh entries,
  proposals aur matches bhi clean karta hai.
- **Na karein:** admin se banayi block row ko complete na samjhein. Usme cleanup
  apne aap nahi hota.

### College invite

<https://whoismycrush.com/802134admin/campus/collegeinvite/>

- **Kab:** weekly.
- **Kyun:** naye college ki asli demand dikhati hai.
- **Karein:** college ban jaye to Approved, na bane to Declined karein.
- **Na karein:** status badalne se email jane ki umeed na karein; aisa nahi hota.

### Notification

<https://whoismycrush.com/802134admin/campus/notification/>

- **Kab:** "mujhe alert aaya" debug karna ho, ya galat alert check karna ho.
- **Kyun:** notification vague rehna chahiye. Yahan leak hua to poora secret khul
  jayega.
- **Karein:** message generic rakhein: "Someone you secretly selected also
  selected you."
- **Na karein:** message mein naam, roll number, priority ya list position na
  daalein.

### Rose

<https://whoismycrush.com/802134admin/campus/rose/>

Rose ka data section system mein bana hua hai, lekin product mein **abhi live
nahi** hai. Koi purchase, payment ya refund flow nahi hai. Students ko rose
promise na karein aur payment manually paid mark na karein. Jab tak asli payment
system na aaye, rows ko chhode rakhein.

### Email verification

<https://whoismycrush.com/802134admin/accounts/emailverification/>

- **Kab:** "link nahi aaya" support, ya email verification on karne se pehle.
- **Kyun:** yeh account email confirm karta hai, campus identity nahi.
- **Karein:** pehle resend karwayein. Ownership confirm hone ke baad hi manually
  verify karein.
- **Na karein:** queue clear karne ke liye poori list verify na karein.

### Blog category and post

<https://whoismycrush.com/802134admin/blog/category/>

<https://whoismycrush.com/802134admin/blog/post/>

Pro Tips likhne ke liye neeche workflow dekhein.

### User (student and admin accounts)

<https://whoismycrush.com/802134admin/auth/user/>

- **Kab:** fake student account band karna ho, ya apna admin account check karna
  ho.
- **Kyun:** access aur audit record.
- **Karein:** account band karna ho to **Is active** untick karein.
- **Na karein:** admin account delete na karein; audit trail toot jayegi. Doosra
  admin account na banayein.

---

## 8. Pro Tips workflow

### Naya category banayein

<https://whoismycrush.com/802134admin/blog/category/add/>

- `name` = public category ka naam.
- `slug` = URL ka last part. Naam se apne aap banta hai; publish ke baad na
  badlein.
- `description` = archive ke upar ek line.
- `accent` = yellow, pink, blue, green ya red.
- `order` = chhota number pehle dikhta hai.

### Post banayein ya edit karein

<https://whoismycrush.com/802134admin/blog/post/add/>

1. **Title** clear aur specific rakhein. Clickbait na karein.
2. **Slug** apne aap banta hai. Publish ke baad stable rakhein.
3. **Category** chunein.
4. **Author name** default WhoIsMyCrush rehta hai. Asli naam sirf permission ke
   baad use karein.
5. **Excerpt** ek-do line, 320 characters tak. Yeh index aur search mein dikhta
   hai.
6. **Cover image** optional hai. JPG, PNG, WEBP ya GIF, 5 MB tak. System ise
   WebP mein badal deta hai aur purani file hata deta hai.
7. **Body** formatting editor mein likhein. Public site script aur bahar ka
   embedded box hata deti hai, isliye raw HTML par bharosa na karein.
8. **Featured** sirf important guides ke liye tick karein.
9. **Publishing:** **Is published** tick karein. Publish date khali ho to abhi
   ka time lagta hai. Future time daal kar schedule kar sakte hain. Server UTC
   time use karta hai, isliye local time ko UTC mein badal kar daalein.
10. **SEO:** SEO title, search description aur canonical URL bharein. Canonical
    URL sirf duplicate content ke liye hai; warna khali chhodein.
11. **Save** karein, phir public post desktop aur mobile par check karein.

**Publishing checklist:**

- [ ] Title aur excerpt natural padh rahe hain.
- [ ] Cover image sahi size aur 5 MB se kam hai.
- [ ] Headings heading style se banayi hain, bold paragraph se nahi.
- [ ] Links sahi page par ja rahe hain.
- [ ] Koi private student info, screenshot ya asli naam nahi hai.
- [ ] SEO title aur description likhe hain.
- [ ] Post sahi category mein hai.
- [ ] Mobile par preview check kiya.
- [ ] **Is published** aur publish date sahi hain.

Post hatana ho to **Is published** untick karein. Row aur slug rehte hain, isliye
baad mein republish kar sakte hain. Public URL tab 404 dega. Delete sirf legal ya
security reason par karein.

---

## 9. Email and notification rules

System kya bhejta hai:

| Kab | Kisko | Rasta | Content |
| --- | --- | --- | --- |
| Signup / resend | Account email | Email | Confirmation link |
| Match approved | Dono students | In-app + email (agar on hai) | "Someone you secretly selected also selected you." |
| Ek student reveal maange | Doosra student | In-app | "Your mutual crush chose to reveal. Open to finish." |
| Report / block | Kisi ko nahi | Kuch nahi | Admin report page se action leta hai |
| Contact form | Admin | Contact messages | Name, email, message, topic, status |

**Kabhi na karein:**

- Notification ya email mein naam, roll number, priority, list position ya
  "kisne pehle chuna" na daalein.
- Student ko email karke na batayein ki kisi ne use crush entry mein likha tha.
  Yeh product ka sabse bada secret hai.
- Match email sirf approval ke baad, ek pair ke liye ek baar, aur
  `MATCH_EMAILS_ENABLED` on hone par jata hai. In-app alert hamesha save hota hai.
- Manual "congratulations" email na bhejein. Product flow use karein.

Email miss ho rahi ho to pehle `check_email` chalayein. Gmail use kar rahe hain to
Email bhejne ke password ki setting mein account password nahi, app password
daalein.

---

## 10. Maintenance commands

Yeh commands project folder se, virtual environment on karke chalayein.
`Terminal` = black command window. `Virtual environment` = project ki alag Python
setting.

| Command | Kab | Kyun | Dobara safe? |
| --- | --- | --- | --- |
| `python manage.py migrate` | Har deploy par | Database structure update | Haan |
| `python manage.py collectstatic --noinput` | Har deploy / editor update | Design aur editor files copy | Haan |
| `python manage.py seed_posts` | Fresh install / content refresh | Shuruaati Pro Tips | Haan |
| `python manage.py seed_colleges` | Fresh install | Starter colleges | Haan |
| `python manage.py seed_colleges --flush` | Sirf test database | Non-starter colleges hatao | **Nahi** |
| `python manage.py seed_demo` | Sirf development | Fake students | **Live par nahi** |
| `python manage.py seed_match` | Sirf development | Demo match + asli alerts | **Live par nahi** |
| `python manage.py check_email --to noreply@whoismycrush.com` | Mail change / weekly | Email system test | Haan |
| `python manage.py check` | Setting change | Configuration galti pakadna | Haan |
| `python manage.py test` | Deploy se pehle / monthly | Automatic safety test | Haan |
| `python manage.py createsuperuser` | Sirf naye server par | Admin account | Zaroorat par |
| `python manage.py shell -c "from campus.services import reconcile_all_matches; print(reconcile_all_matches())"` | Import / miss hone par | Naye proposals queue karna | Haan |
| `python manage.py shell -c "from campus.services import prune_broken_matches; print(prune_broken_matches())"` | Rarely, backup ke baad | Tooti matches delete | Careful |

Shell command ya bade ek-saath edit se pehle database ka backup zaroor lein.

---

## 11. Incident playbook

### Ghalat match approve ho gaya

Email ya alert wapas nahi liya ja sakta. Isliye turant yeh karein:

1. Approved matches page
   (<https://whoismycrush.com/802134admin/campus/mutualmatch/>) par us match ka
   status **Closed** karein, ya **Close selected matches** action use karein.
   Isse reveal flow ruk jata hai.
2. Related proposal rows par note ya correction karein, taaki audit mein reason
   rahe. Purana note delete na karein.
3. Incident record mein likhein: kisne approve kiya, kab, aur kyun galat tha.
   History delete na karein.
4. Affected students ko official support email se chhota, factual apology
   bhejein. Message mein private list detail dobara na likhein.
5. Agar duplicate profile wajah thi, to duplicate pehle theek karein, taaki wahi
   pair dobara propose na ho.

### Duplicate student ya college dikhe

- Student: asli profile pehchan kar duplicate user deactivate karein, sahi
  profile rakhein. Duplicate ki entries zabardasti asli profile par shift na
  karein.
- College: duplicate ki **Is active** untick karein. History ho to delete na
  karein. Incident record mein note likhein.

### Spam ya abuse

1. Reports aur offending accounts check karein.
2. Accounts deactivate karein.
3. Rate limit on hai ya nahi check karein (`RATELIMIT_ENABLE=True`). Rate limit
   ka matlab: ek user bahut zyada requests na bhej sake.
4. Ek college target ho to offending accounts pehle band karein. College inactive
   karne se sirf naye joins rukte hain; purane students kaam karte rehte hain.

### Email outage

1. `python manage.py check_email --to noreply@whoismycrush.com` chalayein.
2. Live site par email bhejne ka system (SMTP) on hai ya nahi check karein.
   Default setting sirf terminal mein mail likhti hai; woh live site ke liye
   kaafi nahi hai.
3. Email ka app password expire hua ho to naya banayein.
4. Email log dekhein.
5. Yaad rakhein: website ke andar ke match alerts email ke bina bhi save hote
   hain, isliye students poori tarah blind nahi hain.

### Queue khali hai par match expect tha

- Dono students ne ek doosre ke liye entry ki hai ya nahi, confirm karein.
- Kisi ne block to nahi kiya, check karein.
- Roll number same format mein hai ya nahi, aur course/year/section contradiction
  to nahi, check karein.
- Matcher command (`reconcile_all_matches`) chalayein. Yeh sirf proposals
  banata hai.
- Us pair ke proposal rows dekhein. Pehle reject hua pair dobara apne aap nahi
  banta.

### Data loss ya security incident

1. Risk ho to website band karein ya nayi entries rok dein.
2. Sabse recent verified backup pehle test server par wapas laayein.
3. Website ki secret key, database password aur email password badal kar naye
   banayein. Secret key badalne se sab users log out ho jayenge.
4. Apna admin account aur recent approval activity check karein.
5. Logs sambhal kar rakhein; evidence delete na karein.

---

## 12. Do and do not

**Karein:**

- Apna naam wala single admin account use karein.
- Har pair kholein aur compare karein, phir approve karein.
- Identity pehle clear karein, match baad mein approve karein.
- Notifications vague rakhein; koi private detail na daalein.
- Users, colleges aur content delete ke bajaye inactive karein.
- Shell command ya bade edit se pehle backup lein.
- Total numbers report karein, kisi ek student ki activity spy na karein.

**Na karein:**

- Kisi ki crush entry, priority ya candidate detail reveal, screenshot ya export
  na karein.
- Sirf naam dekhkar approve na karein. Verified identity dekhein.
- Unresolved identity, one-sided entry, self-match, cross-college pair ya blocked
  pair approve na karein.
- Bina ek-ek row check kiye ek saath approve na karein.
- Approved match ka status haath se Revealed na karein.
- Match proposal ka status haath se approve/reject na karein; actions use karein.
- Email, notification, blog ya support reply mein match data na daalein.
- Admin account delete na karein; audit trail toot jayegi.
- Rose, payment ya aisi feature promise na karein jo live nahi hai.
- Live site par `seed_demo`, `seed_match` ya `seed_colleges --flush` na chalayein.

---

## 13. Cadence summary

| Kab | Kaam |
| --- | --- |
| Har din | Identity candidates, pending match proposals, open reports, contact messages, email verification requests |
| Har hafte | New student profiles, deferred candidates, college data check, invite requests, Pro Tips, backup + email check, `manage.py check` |
| Har mahine | Matcher dobara chalana, tooti matches saaf karna (backup ke baad), automatic tests, duplicate-notification check, sitemap/robots check, growth numbers, admin password check |
| Har quarter | Backup wapas laane ka test, passwords/security keys badalna, supporting software update, content check |

---

## 14. Quick URL reference

Neeche sab real URLs hain. `https://whoismycrush.com` ke baad admin ka rasta
`/802134admin/` hai.

| Kaam | Real URL |
| --- | --- |
| Admin home | <https://whoismycrush.com/802134admin/> |
| Admin login | <https://whoismycrush.com/802134admin/login/> |
| Identity candidates | <https://whoismycrush.com/802134admin/campus/identitycandidate/> |
| Identity audit log | <https://whoismycrush.com/802134admin/campus/identityresolutionaudit/> |
| Crush entries | <https://whoismycrush.com/802134admin/campus/crushentry/> |
| Match proposals | <https://whoismycrush.com/802134admin/campus/potentialmatch/> |
| Approved matches | <https://whoismycrush.com/802134admin/campus/mutualmatch/> |
| Reports | <https://whoismycrush.com/802134admin/campus/report/> |
| Blocks | <https://whoismycrush.com/802134admin/campus/block/> |
| Student profiles | <https://whoismycrush.com/802134admin/campus/studentprofile/> |
| Colleges | <https://whoismycrush.com/802134admin/campus/college/> |
| College invites | <https://whoismycrush.com/802134admin/campus/collegeinvite/> |
| Notifications | <https://whoismycrush.com/802134admin/campus/notification/> |
| Email verification | <https://whoismycrush.com/802134admin/accounts/emailverification/> |
| Contact messages | <https://whoismycrush.com/802134admin/contact/contactmessage/> |
| Pro Tips posts | <https://whoismycrush.com/802134admin/blog/post/> |
| Pro Tips categories | <https://whoismycrush.com/802134admin/blog/category/> |
| Users | <https://whoismycrush.com/802134admin/auth/user/> |
| Public Pro Tips | <https://whoismycrush.com/pro-tips/> |
| Sitemap | <https://whoismycrush.com/sitemap.xml> |
| Robots | <https://whoismycrush.com/robots.txt> |
