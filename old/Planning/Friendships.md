Requirements are detailed [[Requirements#Friendships|here]].

Solutions to meet these requirements:
- To handle friend requests, a table exists with two columns, requester account id and requested account id. When a request is made an entry is made in this table, and when a request is either accepted or rejected the entry is deleted. Friend requests must be unique and cannot have an existing friendship (i.e a request can only be made if for requester A and requested user B there exists no entry if (A,B) in the friendship request or friendship table. Maybe consider it an accept if an entry exists in the friendship request (B,A) since that implies that both users want one; on the other hand the users can just click accept)
- When a friend request is accepted two entries are made in the friendship table: (A,B) and (B,A). This makes it trivial to do friendship lookups at a minor storage / performance cost
- To ensure posts to walls can only be seen if the user is a friend of the user a lookup is done when that wall is accessed before posts are loaded that first checks that a user is a friend and if not sends them to a forbidden page

### [[Tables#Friendships]]
### [[Tables#FriendshipRequests]]
