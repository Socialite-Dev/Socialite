Requirements are detailed [[Requirements#Posts|here]].

Solutions to meet these requirements:
- A user is always able to make posts to their own wall. This can either be done as though posting to someone else's wall if they navigate to their own profile, or through a status update text box on their main feed. No checks need to be done beyond checking that the post target == post author's wall
- To post to someone else's wall a user must be friends with them. To ensure this first to access the text box they have to see the user's wall, which is only possible if they are friends. In addition to stop people circumventing this by directly making a request to the end point the friendship is checked server side as well
- Posts can be made to groups. Again like friends the text box is only available if the user is a member of the group and there is server side validation that it is authorised for that user to post to that group (i.e that they are a member)
- Posts themselves refer to their author, the wall / group they are on and their textual content

I'm a bit unsure on how to handle this but I like the following

### [[Tables#Posts]]
### [[Tables#Walls]]