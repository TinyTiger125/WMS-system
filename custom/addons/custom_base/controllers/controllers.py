# from odoo import http


# class CustomBase(http.Controller):
#     @http.route('/custom_base/custom_base', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_base/custom_base/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_base.listing', {
#             'root': '/custom_base/custom_base',
#             'objects': http.request.env['custom_base.custom_base'].search([]),
#         })

#     @http.route('/custom_base/custom_base/objects/<model("custom_base.custom_base"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_base.object', {
#             'object': obj
#         })

