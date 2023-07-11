#!/usr/bin/python
import array
import math

import numpy as np
from gimpfu import *
import gimp , gimpplugin
pdb = gimp.pdb
import gtk, gimpui, gimpcolor
from gimpshelf import shelf

def to_grayscale ( pixels, bpp ):
    # delete alpha  
    if ( bpp == 2 or bpp == 4 ): 
        pixels = np.delete(pixels, bpp-1, 2 )
    # converte to grayscale if we are in RGB* 
    if ( bpp == 3 or bpp == 4): 
        pixels = np.round(np.dot(pixels[...,:3],[0.229,0.587,0.114]), 0)
    return np.squeeze(pixels)

def create_layer ( image, name, widgth, height, bpp ):
    if bpp == 1:
        return gimp.Layer(image, name, widgth, height, GRAY_IMAGE, 100, NORMAL_MODE)
    elif bpp == 2: 
        return gimp.Layer(image, name, widgth, height, GRAYA_IMAGE, 100, NORMAL_MODE)
    elif bpp == 3:
        return gimp.Layer(image, name, widgth, height, RGB_IMAGE, 100, NORMAL_MODE)
    else:
        return gimp.Layer(image, name, widgth, height, RGBA_IMAGE, 100, NORMAL_MODE)

def index_to_channel_name ( index ): 
    if index == -1: 
        return "GRAY"
    if index == 0: 
        return "RED"
    if index == 1: 
        return "GREEN"
    if index == 2:
        return "BLUE"
    else:
        return "None"

def channel_name_to_index ( name ): 
    if name == "GRAY": 
        return -1
    elif name == "RED": 
        return 0
    elif name == "GREEN":
        return 1 
    elif name == "BLUE": 
        return 2 
    else:
        return -2

class lbp_plugin(gimpplugin.plugin):
    shelf_key = "lbp_plugin"
    lbp_radius = 0
    histogram = {
    
    }
    histogram_filepath = ""
    is_dump_histogram = False 

    def query(self):
        gimp.install_procedure(
            "lbp_plugin_main",
            "Calculates local binary patterns",
            "Calculates local binary patterns",
            "Andrey Cherkasov",
            "Andrey Cherkasov",
            "2022",
            "<Image>/_Xtns/Local binary patterns",
            "RGB*, GRAY*",
            PLUGIN,
            [
                #next three parameters are common for all scripts that are inherited from gimpplugin.plugin
                (PDB_INT32, "run_mode", "Run mode"),
                (PDB_IMAGE, "image", "Input image"),
                (PDB_DRAWABLE, "drawable", "Input drawable"),
                #plugin specific parameters
                (PDB_INT32, "lbp_radius", "Radius for LBP"),
            ],
            []
        )

    def start(self):
        gimp.main(self.init, self.quit, self.query, self._run)

    def init(self):
        pass

    def quit(self):
        pass

    def lbp_plugin_main(self, run_mode, image, drawable, lbp_radius = 1):
        self.image = image
        self.drawable = drawable

		#create settings if doesn't exist storage
        if not shelf.has_key(self.shelf_key):
            self.shelf_store(lbp_radius)
        self.create_dialog()

        # Allows to discard changes doing "undo"
        pdb.gimp_image_undo_group_start(self.image)
		# if threre is editor => run UI, otherwise run shifting
        if run_mode == RUN_INTERACTIVE:
            self.dialog.run()
        else:
            self.calculate_lbp()
        pdb.gimp_image_undo_group_end(self.image)

        

    def shelf_store ( self, lbp_radius, is_lbp_red_channel = True, is_lbp_green_channel = True, is_lbp_blue_channel = True, is_dump_histogram = False, histogram_filepath = "" ):
        shelf[self.shelf_key] = {
            "lbp_radius":lbp_radius,
            "is_lbp_red_channel":is_lbp_red_channel,
            "is_lbp_green_channel":is_lbp_green_channel,
            "is_lbp_blue_channel":is_lbp_blue_channel,	
            "is_dump_histogram":is_dump_histogram,
            "histogram_filepath":histogram_filepath
        }
    def is_channel_active ( self, index ): 
        if index == 0 and self.is_lbp_red_channel:
            return True
        if index == 1 and self.is_lbp_green_channel:
            return True
        if index == 2 and self.is_lbp_blue_channel:
            print
            return True
        else:
            return False


    def calculate_lbp_internal ( self, dst_pixels, pixel_matrix, bw, bh, channel_name = "GRAY" ):
        radius = self.lbp_radius
        channels = 3 if len(pixel_matrix.shape) == 3 else 1
        channel_pixels = pixel_matrix 
        channel_index = channel_name_to_index ( channel_name )
        if channel_index != -1: 
            channel_pixels = pixel_matrix [:,:,channel_index]
        # I guess GIMP doesn't have python impl for progress_end() function and reiniting a progress bar with different name doesn't actually change a name :/ 
        # So i can't do a progress bar with different names for each channel
        gimp.progress_init("Processing channel : " + channel_name )
        for x in range (radius, bh + radius):
            for y in range (radius, bw + radius):
                pos = ( ( x - radius ) * bw + y - radius) * channels
                binary_values = []

                data = channel_pixels[x - radius: x + 1 + radius:radius,
                                y - radius: y + 1 + radius:radius ]
                data = data.ravel()
                center = data[4]
                indexesNeeded = [0,1,2,3,5,6,7,8]
                for i in indexesNeeded: 
                    if data [ i ] > center: 
                        binary_values.append(0)
                    else:
                        binary_values.append(1)
                st = "".join( ( str ( val ) for val in binary_values ))

                # dump histogram if needed
                if self.is_dump_histogram:
                    if channel_name in self.histogram:
                        if st in self.histogram[channel_name]: 
                            self.histogram[channel_name][st] += 1
                        else:
                            self.histogram[channel_name][st] = 1 
                    else:
                        self.histogram[channel_name] = {}
                        self.histogram[channel_name][st] = 1
                    

                res = int ( st, 2 )
                for k in range ( 0, channels ):
                    dst_pixels[pos + k] = res
            gimp.progress_update(float(x+1)/bh)

    def lbp_for_channel ( self, channel_name, src_pixels, bw, bh ):
        bpp = self.drawable.bpp
        (bx1, by1, bx2, by2) = self.drawable.mask_bounds
        (ox, oy) = self.drawable.offsets
        layer = create_layer ( self. image, channel_name + " R = " + str(self.lbp_radius), bw, bh, bpp )
        layer . set_offsets ( bx1 + ox, by1 + oy )
        self . image. add_layer ( layer, 0 )
        dst_rgn = layer . get_pixel_rgn ( 0,0, bw, bh, True, True )
        dst_pixels = array.array ( "B", dst_rgn [0:bw, 0:bh] )
        self.calculate_lbp_internal( dst_pixels, src_pixels, bw, bh, channel_name )
        dst_rgn[0:bw, 0:bh] = dst_pixels.tostring()
        layer . flush() 
        layer . merge_shadow ( True )
        layer . update ( 0, 0, bw , bh )
        gimp.displays_flush()


    def calculate_lbp ( self ):
        # get info from drawable
        (bx1, by1, bx2, by2) = self.drawable.mask_bounds
        bpp = self.drawable.bpp
        bw = bx2 - bx1
        bh = by2 - by1
        radius = self.lbp_radius
        # check if drawable is valid
        if bw == 0 or bh == 0:
            gimp.message("Bad selection. Probably your selection is out of bounce of current layer")
            return


        # bind to input
        src_rgn = self.drawable.get_pixel_rgn(bx1, by1, bw, bh, False, False)
        src_pixels = array.array("B", src_rgn[bx1:bx2, by1:by2])
        # Convert 1D array to numpy matrix  
        if bpp == 1:
            src_pixels = np.reshape ( src_pixels, (-1, bw) )
        if bpp > 2:
            src_pixels = np.reshape ( src_pixels, (-1, bw, bpp ) )
        # Remove alpha
        if bpp == 2 or bpp == 4: 
            src_pixels = np.delete( src_pixels, bpp - 1, 2 )
            src_pixels = np.squeeze(src_pixels)
        
        pad_shape = radius
        if bpp > 2: 
            pad_shape = ((radius, radius), (radius, radius), (0, 0))
        # Pad the matrix with symmetric mirrored values
        src_pixels = np.pad( src_pixels, pad_shape, 'symmetric' )

        if bpp == 1 or bpp == 2:
            self.lbp_for_channel ( "GRAY", src_pixels, bw, bh )
        else: 
            for channel in range ( 0, 3 ): 
                if self.is_channel_active ( channel ):
                    self.lbp_for_channel ( index_to_channel_name ( channel ), src_pixels, bw, bh )
        
        if self.is_dump_histogram:
            try: 
                file = open (self.histogram_filepath, 'w' )
                for channel in self.histogram:
                    file . write ( "-- " +str(channel) + " channel histogram. Radius = " + str(radius) + " --\n") 
                    for key in sorted(self.histogram[channel], key = self.histogram[channel].get, reverse = True ): 
                        file . write ( key + ":" + str(self.histogram[channel][key]) + "\n" )
                file . close() 
            except IOError:
                gimp.message ("Error: can't write histogram.\nFile: \"" + self.histogram_filepath + "\" doesn't exist or can't be opened") 

        return





        
    def create_dialog( self ):
        self.dialog = gimpui.Dialog("LBP", "Local binary patterns")
		#3x2 non-homogenous table
        n_rows = 4
        if ( self.drawable.bpp > 2 ):
            n_rows = 7
        self.table = gtk.Table(n_rows, 2, False)
        self.table.set_row_spacings(8)
        self.table.set_col_spacings(8)
        self.table.show()

        # LBP label
        self.lbp_label = gtk.Label("LBP radius: ")
        self.lbp_label.set_alignment(0.5, 0.5)
        self.lbp_label.show()
        self.table.attach(self.lbp_label, 0, 1, 0, 1)

        # LBP scale button
        self.radius_adj = gtk.Adjustment(0, 0, 50, 1)
        self.scaleRadiusButton = gtk.SpinButton(self.radius_adj, 1)
        self.scaleRadiusButton.set_value(shelf[self.shelf_key]["lbp_radius"])
        self.scaleRadiusButton.connect("value_changed",self.on_radius_changed)
        self.scaleRadiusButton.show()
        self.table.attach(self.scaleRadiusButton, 1, 2, 0, 1)

        # If image is RGB*
        if ( self.drawable.bpp > 2 ):
            # Red channel button 
            self.redChannelCheckBox = gtk.CheckButton ("LBP for Red Channel")
            self.redChannelCheckBox.set_active(int(shelf[self.shelf_key]["is_lbp_red_channel"]))
            self.redChannelCheckBox.show()
            self.table.attach(self.redChannelCheckBox, 0, 2, 1, 2)

            # Green channel button
            self.greenChannelCheckBox = gtk.CheckButton ("LBP for Green Channel")
            self.greenChannelCheckBox.set_active(int(shelf[self.shelf_key]["is_lbp_green_channel"]))
            self.greenChannelCheckBox.show()
            self.table.attach(self.greenChannelCheckBox, 0, 2, 2, 3)

            # Blue channel button
            self.blueChannelCheckBox = gtk.CheckButton ("LBP for Blue Channel")
            self.blueChannelCheckBox.set_active(int(shelf[self.shelf_key]["is_lbp_blue_channel"]))
            self.blueChannelCheckBox.show()
            self.table.attach(self.blueChannelCheckBox, 0, 2, 3, 4)

        # Histogram checkbox
        histogram_col_attach = None
        if ( self.drawable . bpp > 2 ):
            histogram_col_attach = (4, 5)
        else:
            histogram_col_attach = (1, 2)

        self.histogramCheckBox = gtk.CheckButton ("Dump histogram")
        self.histogramCheckBox.set_active(shelf[self.shelf_key]["is_dump_histogram"])
        self.histogramCheckBox.show()
        self.table.attach(self.histogramCheckBox, 0, 2, histogram_col_attach[0], histogram_col_attach[1])

        # Histogram label
        self.histogramFilepathLabel = gtk.Label ("Histogram filepath: ")
        self.histogramFilepathLabel.set_alignment(0.5,0.5)
        self.histogramFilepathLabel.show()
        self.table.attach (self.histogramFilepathLabel, 0, 1, histogram_col_attach[0] + 1, histogram_col_attach[1] + 1)


        # Histogram file entry 
        self.histogramFilepathEntry = gtk.Entry()
        self.histogramFilepathEntry.set_text(shelf[self.shelf_key]["histogram_filepath"])
        self.histogramFilepathEntry.connect ("changed", self.on_histogram_filepath_changed )
        self.histogramFilepathEntry.show()
        self.table.attach(self.histogramFilepathEntry, 1, 2, histogram_col_attach[0] + 1, histogram_col_attach[1] + 1)


        # Cancel button
        self.cancelButton = gtk.Button("Cancel")
        self.cancelButton.show()
        self.cancelButton.connect("clicked", self.on_cancel_clicked)
        self.table.attach(self.cancelButton, 1, 2, histogram_col_attach[0] + 2, histogram_col_attach[1] + 2)

		# Ok button
        self.okButton = gtk.Button("OK")
        self.okButton.show()
        self.okButton.connect("clicked", self.on_ok_clicked)
        self.table.attach(self.okButton, 0, 1, histogram_col_attach[0] + 2, histogram_col_attach[1] + 2)

        # there is a table inside a hbox inside a vbox
        self.dialog.vbox.hbox1 = gtk.HBox(False, 7)
        self.dialog.vbox.hbox1.show()
        self.dialog.vbox.pack_start(self.dialog.vbox.hbox1, True, True, 7)
        self.dialog.vbox.hbox1.pack_start(self.table, True, True, 7)


    def on_histogram_filepath_changed ( self, widget ):
        self.histogram_filepath = self.histogramFilepathEntry.get_text()

    def on_radius_changed ( self, widget ):
        self.lbp_radius = int(self.scaleRadiusButton.get_value())

    def on_ok_clicked ( self, widget ):
        self.histogram_filepath = self.histogramFilepathEntry.get_text()
        self.lbp_radius = int(self.scaleRadiusButton.get_value())
        self.is_dump_histogram = self.histogramCheckBox.get_active()
        # save settings depending on bpp of the image
        if ( self.drawable.bpp < 3  ): 
            self.shelf_store (  self.lbp_radius, 
                                shelf[self.shelf_key]["is_lbp_red_channel"],
                                shelf[self.shelf_key]["is_lbp_green_channel"],
                                shelf[self.shelf_key]["is_lbp_blue_channel"], 
                                self.is_dump_histogram,                                                
                                self.histogram_filepath )
        else:
            self.is_lbp_red_channel = self.redChannelCheckBox . get_active()
            self.is_lbp_green_channel = self.greenChannelCheckBox . get_active()
            self.is_lbp_blue_channel = self.blueChannelCheckBox . get_active()
            self.shelf_store (  self.lbp_radius, 
                                self.is_lbp_red_channel,
                                self.is_lbp_green_channel,
                                self.is_lbp_blue_channel, 
                                self.is_dump_histogram,                                                
                                self.histogram_filepath )

        self.calculate_lbp()
        pdb.gimp_image_undo_group_end(self.image)
        gimp.quit()

    def on_cancel_clicked ( self, widget ):
        pdb.gimp_image_undo_group_end(self.image)
        gimp.quit()



        
        
if __name__ == '__main__':
    lbp_plugin().start()
