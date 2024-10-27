Requirements are detailed [[Requirements#Accounts|here]].

Solutions to meet these requirements:
-  To allow logging in and out the accounts need to have a username (maybe just actual student name) field as well as a password field (containing an argon2 password hash)
- To allow passwords to be changed, on the login page a button allows a user to request a password change from a teacher. This creates a flag on their account that means a teacher can approve their password change (maybe notifies them?). If a teacher approves the change then the initial flag is removed their password is changed to a randomly generated one the teacher can see, and another flag is set on their account that lets them change their password the next time they log in. (That last flag + provided password mechanism is the same at account creation)
- To allow accounts to be created a teacher can make an account by providing a name (and possibly an email). This initialises an account with a random password, and a flag to change that password on next login
- To allow accounts to be created en-masse an option exists to provide a CSV of name (optional email) to create an account for every entry (initalised as above) 
- For each user a teacher has access to delete their account. To stop this from happening by accident a pop up box will request that the teacher type out the user's full name. (Potentially to delete a teacher's account multiple teachers must agree?)
- To differentiate teachers from students there is a boolean flag on the account that is true if the user is a teacher

### [[Tables#Accounts]]