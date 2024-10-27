##### Accounts
id: integer (PK, AI)
username: text (U, NN)
password: text (NN)
password reset on next login: boolean (NN)
student requests password change: boolean (NN)
is teacher: boolean (NN)
email: text (expected, but not required, to be null if and only if the account is associated with a student who is not assigned a school email - for instance if they're at a primary school)

##### Friendships
id: integer (PK, AI)
first user: integer (NN, FK "accounts.id")
second user: integer (NN, FK "accounts.id")

##### Friendship Requests
id: integer (PK, AI)
first user: integer (NN, FK "accounts.id")
second user: integer (NN, FK "accounts.id")

##### Posts
id: integer (PK, AI)
content: text (NN)
author: integer (NN, FK "accounts.id")
wall: integer (NN, FK "walls.id")

##### Walls
id: integer (PK, AI)
type: text (NN, type is something like a union of the literals "user", "group")
user: integer(FK "accounts.id", non null if and only if type = "user")
group: integer(FK "groups.id", non null if and only if type = "group")

#### Groups
id: integer (PK)
name: text
owner: integer (FK "accounts.id")

#### GroupMembers
id: integer (PK, AI)
user: integer (FK "accounts.id")
group: integer (FK "groups.id")